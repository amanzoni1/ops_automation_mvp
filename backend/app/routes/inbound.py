import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import models
from app.db.session import get_db
from app.schemas.inbound import InboundEvent, InboundResponse
from app.services.ai import extract_task_fields, generate_enrichment
from app.services.audit import log_action
from app.services.knowledge_base import retrieve_chunks
from app.services.n8n_client import post_outbound
from app.services.rag import answer_with_confidence
from app.services.router import route_channel
from app.services.task_service import create_task_with_enrichment
from app.services.todoist_client import TodoistClient

logger = logging.getLogger(__name__)

router = APIRouter()

def _clean_user(value: str | None) -> str | None:
    if not value:
        return None
    if value.strip().lower() in {"none", "null", ""}:
        return None
    return value


@router.post("/inbound", response_model=InboundResponse)
async def inbound(event: InboundEvent, session: AsyncSession = Depends(get_db)) -> InboundResponse:
    route_info = route_channel(event.source_channel)
    sender_user = _clean_user(event.sender_user) or _clean_user(settings.inbound_default_sender) or _clean_user(event.source_user)
    receiver_user = _clean_user(event.receiver_user) or _clean_user(settings.inbound_default_receiver) or _clean_user(event.source_user)

    inbox = models.InboxEvent(
        source=event.source,
        source_channel=event.source_channel,
        source_user=event.source_user,
        sender_user=sender_user,
        receiver_user=receiver_user,
        thread_id=event.thread_id,
        text=event.text,
        raw_json=event.model_dump(mode="json"),
        pipeline=route_info["pipeline"],
        intake_tier=route_info["intake_tier"],
    )
    session.add(inbox)
    await session.commit()

    actor_user = sender_user or event.source_user
    await log_action(
        session,
        actor=f"user:{actor_user}" if actor_user else "system",
        action="inbound_received",
        entity_type="inbox_event",
        entity_id=inbox.id,
        details={"pipeline": route_info["pipeline"]},
    )

    if route_info["pipeline"] == "sop_qa":
        chunks = await retrieve_chunks(session, event.text)
        answer_data = await answer_with_confidence(event.text, chunks)
        confidence = float(answer_data.get("confidence", 0.0))
        if confidence > 0.85:
            tier = "auto"
            prefix = ""
        elif confidence >= 0.50:
            tier = "flagged"
            prefix = "I'm fairly confident, but flagging for review. "
        else:
            tier = "low_confidence"
            prefix = "Low confidence. Answer may be incomplete: "
        answer = answer_data.get("answer") or ""

        outbound_payload = {
            "action": "send_slack_message",
            "channel": event.source_channel,
            "thread_id": event.thread_id,
            "text": f"{prefix}{answer}",
            "sender_user": sender_user,
            "receiver_user": receiver_user,
        }
        await post_outbound(outbound_payload, session=session)
        await log_action(
            session,
            actor="ai:rag",
            action="rag_answered",
            entity_type="inbox_event",
            entity_id=inbox.id,
            details={"confidence": confidence, "tier": tier},
        )
        details = {"outbound": outbound_payload} if settings.debug_echo_outbound else None
        return InboundResponse(status="answered", pipeline=route_info["pipeline"], message=answer, details=details)

    if not settings.todoist_api_token:
        raise HTTPException(status_code=400, detail="Todoist API token not configured")

    todoist_client = TodoistClient(settings.todoist_api_token)
    extracted_fields = await extract_task_fields(event.text, route_info["pipeline"])
    assignee = extracted_fields.get("assignee")
    if isinstance(assignee, str) and assignee.strip().lower() in {"none", "null", ""}:
        assignee = None
    if receiver_user and not assignee:
        extracted_fields["assignee"] = receiver_user
    logger.info(
        "Inbound assignment",
        extra={"source_user": event.source_user, "assignee": extracted_fields.get("assignee")},
    )
    chunks = await retrieve_chunks(session, event.text, k=6)
    enrichment_tips = await generate_enrichment(event.text, chunks)

    task_record = await create_task_with_enrichment(
        session=session,
        todoist_client=todoist_client,
        extracted_fields=extracted_fields,
        enrichment_tips=enrichment_tips,
        inbox_event_id=inbox.id,
        task_type=route_info["pipeline"],
    )

    message = f"📌 New task assigned: '{task_record.title}'. Please review in Todoist."
    outbound_payload = {
        "action": "send_slack_message",
        "channel": event.source_channel,
        "thread_id": event.thread_id,
        "text": message,
        "sender_user": sender_user,
        "receiver_user": receiver_user,
    }
    await post_outbound(outbound_payload, session=session)

    details = {"outbound": outbound_payload} if settings.debug_echo_outbound else None
    return InboundResponse(status="created", pipeline=route_info["pipeline"], message=message, details=details)
