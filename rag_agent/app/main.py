from __future__ import annotations
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from langchain_openai import ChatOpenAI
from app.config import settings
from app.db import AsyncSessionLocal
from app.knowledge_base import retrieve_chunks


app = FastAPI(title="RAG Agent Service")


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    confidence: float


def _keywords(query: str) -> list[str]:
    tokens = [t.strip().lower() for t in query.replace("?", " ").split()]
    return [t for t in tokens if len(t) > 3]


def _compute_confidence(query: str, chunks: list[dict[str, Any]]) -> float:
    if not chunks:
        return 0.0
    max_similarity = max(chunk.get("similarity", 0.0) for chunk in chunks)
    terms = _keywords(query)
    if terms:
        hit = any(
            any(term in (c.get("chunk_text") or "").lower() for term in terms)
            for c in chunks
        )
        if hit:
            max_similarity = min(1.0, max_similarity + 0.1)
    return max_similarity


def _dedupe_citations(query: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = _keywords(query)
    seen: set[tuple[str | None, str | None, str | None]] = set()
    citations: list[dict[str, Any]] = []
    sorted_chunks = sorted(chunks, key=lambda c: c.get("similarity", 0.0), reverse=True)
    for c in sorted_chunks:
        chunk_text = c.get("chunk_text") or ""
        section = c.get("section_ref")
        if chunk_text.strip().startswith("#") and not section:
            continue
        if terms and not any(term in chunk_text.lower() for term in terms):
            continue
        key = (c.get("doc_title"), section, chunk_text)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "source": c.get("doc_title"),
                "section": section,
                "chunk": chunk_text,
            }
        )
        if len(citations) >= 2:
            break
    if citations:
        return citations
    for c in sorted_chunks[:2]:
        citations.append(
            {
                "source": c.get("doc_title"),
                "section": c.get("section_ref"),
                "chunk": c.get("chunk_text"),
            }
        )
    return citations


async def _answer_with_context(query: str, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "I couldn't find a policy covering this."

    context_blob = "\n\n".join(
        f"[{c.get('doc_title')} {c.get('section_ref')}] {c.get('chunk_text')}"
        for c in chunks
    )
    system_prompt = (
        "You are a strict policy assistant for a Family Office. "
        "Use ONLY the provided context. Never guess or invent policies. "
        "Answer concisely and in a structured way (short title + bullet points if helpful). "
        "Always include a short 'Source:' line at the end with document name and section."
    )
    user_prompt = (
        "Question: {query}\n\n"
        "Context:\n{context_blob}\n\n"
        "If the context does not answer the question, reply exactly: "
        "\"I couldn't find a policy covering this.\""
    ).format(query=query, context_blob=context_blob)

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    response = await llm.ainvoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return (response.content or "").strip()


@app.post("/answer", response_model=AskResponse)
async def answer(request: AskRequest) -> AskResponse:
    async with AsyncSessionLocal() as session:
        chunks = await retrieve_chunks(session, request.query, k=6)

    content = await _answer_with_context(request.query, chunks)

    confidence = _compute_confidence(request.query, chunks)
    citations = _dedupe_citations(request.query, chunks)

    return AskResponse(answer=content, citations=citations, confidence=confidence)
