from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any

from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


def _get_llm(*, temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=temperature,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
    )


def _get_llm_json() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0.0,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _clamp_priority(value: Any) -> int:
    try:
        val = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(4, val))


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}
        return {}


def _infer_due_date(text: str) -> str | None:
    lower = text.lower()
    today = date.today()

    if any(token in lower for token in ["today", "eod", "end of day", "midday", "noon", "by lunch"]):
        return today.isoformat()
    if "tomorrow" in lower:
        return (today + timedelta(days=1)).isoformat()
    if "next week" in lower:
        return (today + timedelta(days=7)).isoformat()

    weekdays = [
        ("monday", 0),
        ("tuesday", 1),
        ("wednesday", 2),
        ("thursday", 3),
        ("friday", 4),
        ("saturday", 5),
        ("sunday", 6),
    ]
    for name, idx in weekdays:
        if f"next {name}" in lower:
            days_ahead = (idx - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (today + timedelta(days=days_ahead)).isoformat()
    for name, idx in weekdays:
        if f"on {name}" in lower or f"by {name}" in lower:
            days_ahead = (idx - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (today + timedelta(days=days_ahead)).isoformat()

    return None


async def extract_task_fields(text: str, pipeline: str | None) -> dict[str, Any]:
    llm = _get_llm_json()
    system_prompt = (
        "Extract task fields from the message. Return JSON only with keys: "
        "title, summary, priority (1-4), due_date (YYYY-MM-DD or null), "
        "labels (list), assignee (string or null), "
        "key_details (list of short strings), "
        "questions (list of missing info), "
        "subtasks (list of short action items)."
    )
    user_prompt = (
        f"Message: {text}\n"
        f"Pipeline: {pipeline or 'general'}\n"
        "If unsure, set priority=3, labels=[pipeline], due_date=null.\n"
        "Return ONLY valid JSON."
    )

    try:
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        data = _extract_json(response.content or "{}")
    except Exception as exc:
        logger.warning("Task extraction failed, using fallback", exc_info=exc)
        data = {}

    labels = data.get("labels")
    if isinstance(labels, str):
        labels = [labels]
    if not isinstance(labels, list) or not labels:
        labels = [pipeline or "general"]

    title = data.get("title") or text.strip()[:80] or "Untitled task"
    summary = data.get("summary") or title
    key_details = data.get("key_details") or []
    questions = data.get("questions") or []
    subtasks = data.get("subtasks") or []

    if isinstance(key_details, str):
        key_details = [key_details]
    if isinstance(questions, str):
        questions = [questions]
    if isinstance(subtasks, str):
        subtasks = [subtasks]

    description_lines = [f"Summary: {summary}"]
    if key_details:
        description_lines.append("Key details:")
        description_lines.extend([f"- {item}" for item in key_details])
    if questions:
        description_lines.append("Missing info / questions:")
        description_lines.extend([f"- {item}" for item in questions])
    if subtasks:
        description_lines.append("Suggested subtasks:")
        description_lines.extend([f"- {item}" for item in subtasks])
    description_lines.append(f"Source message: {text}")

    due_date = data.get("due_date") or _infer_due_date(text)

    priority = _clamp_priority(data.get("priority"))
    lower_text = text.lower()
    if any(token in lower_text for token in ["high priority", "urgent", "asap", "immediately", "critical"]):
        priority = 4
    elif "medium priority" in lower_text:
        priority = max(priority, 3)
    elif "low priority" in lower_text:
        priority = min(priority, 2)

    assignee = data.get("assignee")
    if isinstance(assignee, str) and assignee.strip().lower() in {"none", "null", ""}:
        assignee = None

    return {
        "title": title,
        "priority": priority,
        "due_date": due_date,
        "labels": labels,
        "assignee": assignee,
        "description": "\n".join(description_lines),
    }


async def generate_enrichment(task_text: str, chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No relevant SOP tips found."

    context_blob = "\n\n".join(
        f"[{chunk.get('doc_title')} {chunk.get('section_ref')}] {chunk.get('chunk_text')}"
        for chunk in chunks
    )
    system_prompt = (
        "You are an operations assistant. Using ONLY the provided context, produce "
        "a compact checklist with source tags. Format exactly:\n"
        "Checklist:\n"
        "- item [Doc §X]\n"
        "Required fields:\n"
        "- item [Doc §X]\n"
        "Approvals / exceptions:\n"
        "- item [Doc §X]\n"
        "If nothing relevant, reply: No relevant SOP tips found."
    )
    user_prompt = f"Task: {task_text}\n\nContext:\n{context_blob}"

    llm = _get_llm(temperature=0.1)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    return (response.content or "").strip()
