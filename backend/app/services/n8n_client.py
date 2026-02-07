import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.audit import log_action

logger = logging.getLogger(__name__)


async def post_outbound(payload: dict[str, Any], session: AsyncSession | None = None) -> None:
    if not settings.n8n_outbound_webhook_url:
        logger.warning("N8N_OUTBOUND_WEBHOOK_URL not set; skipping outbound message")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            logger.info("Outbound payload", extra={"payload": payload})
            resp = await client.post(settings.n8n_outbound_webhook_url, json=payload)
            resp.raise_for_status()
            if session is not None:
                await log_action(
                    session,
                    actor="system",
                    action="outbound_sent",
                    details={"action": payload.get("action"), "channel": payload.get("channel")},
                )
        except Exception as exc:
            logger.exception("Failed to post outbound message", exc_info=exc)
            return
