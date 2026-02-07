from __future__ import annotations

import random
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.config import settings


def _mock_vector(text_value: str, dim: int = 1536) -> list[float]:
    seed = abs(hash(text_value)) % (2**32)
    rng = random.Random(seed)
    return [rng.random() for _ in range(dim)]


def _keywords(query: str) -> list[str]:
    tokens = [t.strip().lower() for t in query.replace("?", " ").split()]
    return [t for t in tokens if len(t) > 3]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        return [_mock_vector(text_value) for text_value in texts]

    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
    )
    return await embeddings.aembed_documents(texts)


async def _vector_search(
    session: AsyncSession,
    query: str,
    k: int,
    min_similarity: float,
) -> list[dict[str, Any]]:
    embedding = (await embed_texts([query]))[0]
    stmt = text(
        """
        SELECT kc.chunk_text, kc.section_ref, kd.title as doc_title,
               1 - (kc.embedding <=> :embedding) AS similarity
        FROM kb_chunks kc
        JOIN kb_docs kd ON kd.id = kc.doc_id
        ORDER BY kc.embedding <=> :embedding
        LIMIT :k
        """
    ).bindparams(bindparam("embedding", type_=Vector(1536)))
    result = await session.execute(stmt, {"embedding": embedding, "k": k})
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in result.fetchall():
        similarity = float(row.similarity or 0.0)
        if similarity < min_similarity:
            continue
        if row.chunk_text in seen:
            continue
        seen.add(row.chunk_text)
        chunks.append(
            {
                "chunk_text": row.chunk_text,
                "section_ref": row.section_ref,
                "doc_title": row.doc_title,
                "similarity": similarity,
            }
        )
    return chunks


async def _keyword_search(session: AsyncSession, query: str, k: int) -> list[dict[str, Any]]:
    terms = _keywords(query)
    if not terms:
        return []
    like_clauses = " OR ".join(["kc.chunk_text ILIKE :t" + str(i) for i in range(len(terms))])
    params = {"t" + str(i): f"%{term}%" for i, term in enumerate(terms)}
    stmt = text(
        f"""
        SELECT kc.chunk_text, kc.section_ref, kd.title as doc_title,
               0.0 AS similarity
        FROM kb_chunks kc
        JOIN kb_docs kd ON kd.id = kc.doc_id
        WHERE {like_clauses}
        LIMIT :k
        """
    )
    params["k"] = k
    result = await session.execute(stmt, params)
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in result.fetchall():
        if row.chunk_text in seen:
            continue
        seen.add(row.chunk_text)
        chunks.append(
            {
                "chunk_text": row.chunk_text,
                "section_ref": row.section_ref,
                "doc_title": row.doc_title,
                "similarity": 0.0,
            }
        )
    return chunks


async def retrieve_chunks(
    session: AsyncSession,
    query: str,
    k: int = 6,
    min_similarity: float = 0.05,
) -> list[dict[str, Any]]:
    vector_chunks = await _vector_search(session, query, k, min_similarity)
    keyword_chunks = await _keyword_search(session, query, k)

    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for chunk in vector_chunks + keyword_chunks:
        text_value = chunk.get("chunk_text") or ""
        if text_value in seen:
            continue
        seen.add(text_value)
        merged.append(chunk)
        if len(merged) >= k:
            break
    return merged
