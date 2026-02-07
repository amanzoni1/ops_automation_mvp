from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


async def answer_with_confidence(query: str, _: list[dict[str, Any]]) -> dict[str, Any]:
    if not settings.rag_agent_url:
        return {
            "answer": "RAG service unavailable. Please configure RAG_AGENT_URL.",
            "citations": [],
            "confidence": 0.0,
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(settings.rag_agent_url, json={"query": query})
            resp.raise_for_status()
            data = resp.json()
            return {
                "answer": data.get("answer", ""),
                "citations": data.get("citations", []),
                "confidence": float(data.get("confidence", 0.0)),
            }
    except Exception:
        return {
            "answer": "RAG service unavailable. Please try again later.",
            "citations": [],
            "confidence": 0.0,
        }
