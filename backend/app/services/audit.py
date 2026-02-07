from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models


async def log_action(
    session: AsyncSession,
    actor: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    entry = models.AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(entry)
    await session.commit()
