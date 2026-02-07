from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.ask import AskRequest, AskResponse
from app.services.audit import log_action
from app.services.n8n_client import post_outbound
from app.services.rag import answer_with_confidence
from app.services.knowledge_base import retrieve_chunks

router = APIRouter()


def _tier_from_confidence(confidence: float) -> str:
    if confidence >= 0.75:
        return "auto"
    if confidence >= 0.45:
        return "flagged"
    return "low_confidence"


def _format_answer(answer_text: str) -> tuple[str | None, list[str], str | None]:
    if not answer_text:
        return None, [], None
    lines = [line.strip() for line in answer_text.splitlines() if line.strip()]
    if not lines:
        return None, [], None
    title = lines[0]
    bullets: list[str] = []
    source: str | None = None
    for line in lines[1:]:
        if line.lower().startswith("source:"):
            source = line
            continue
        if line.startswith("- "):
            bullets.append(line[2:])
    return title, bullets, source


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, session: AsyncSession = Depends(get_db)) -> AskResponse:
    chunks = await retrieve_chunks(session, request.query)
    answer_data = await answer_with_confidence(request.query, chunks)

    confidence = float(answer_data.get("confidence", 0.0))
    answer_text = answer_data.get("answer", "")
    tier = _tier_from_confidence(confidence)

    answer_with_tier = answer_text

    await log_action(
        session,
        actor="ai:rag",
        action="rag_answered",
        details={"confidence": confidence, "tier": tier, "user_id": request.user_id},
    )

    if request.source_channel and request.thread_id:
        await post_outbound(
            {
                "action": "send_slack_message",
                "channel": request.source_channel,
                "thread_id": request.thread_id,
                "text": answer_with_tier,
            },
            session=session,
        )
    if request.user_id:
        await post_outbound(
            {
                "action": "send_slack_dm",
                "user_id": request.user_id,
                "text": answer_text,
            },
            session=session,
        )

    answer_title, answer_bullets, answer_source = _format_answer(answer_text)
    return AskResponse(
        answer=answer_text,
        answer_title=answer_title,
        answer_bullets=answer_bullets,
        answer_source=answer_source,
        citations=answer_data.get("citations", []),
        confidence=confidence,
        tier=tier,
    )
