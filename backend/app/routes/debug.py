from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import get_db

router = APIRouter()


@router.get("/debug/db")
async def db_snapshot(
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    audit_result = await session.execute(
        select(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit)
    )
    inbox_result = await session.execute(
        select(models.InboxEvent).order_by(models.InboxEvent.created_at.desc()).limit(limit)
    )
    task_result = await session.execute(
        select(models.Task).order_by(models.Task.created_at.desc()).limit(limit)
    )
    enforce_result = await session.execute(
        select(models.EnforcementLog).order_by(models.EnforcementLog.created_at.desc()).limit(limit)
    )

    return {
        "audit_log": [
            {
                "id": str(row.id),
                "actor": row.actor,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id) if row.entity_id else None,
                "details": row.details,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in audit_result.scalars().all()
        ],
        "inbox_events": [
            {
                "id": str(row.id),
                "source": row.source,
                "source_channel": row.source_channel,
                "source_user": row.source_user,
                "sender_user": row.sender_user,
                "receiver_user": row.receiver_user,
                "thread_id": row.thread_id,
                "pipeline": row.pipeline,
                "intake_tier": row.intake_tier,
                "text": row.text,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in inbox_result.scalars().all()
        ],
        "tasks": [
            {
                "id": str(row.id),
                "todoist_id": row.todoist_id,
                "title": row.title,
                "task_type": row.task_type,
                "priority": row.priority,
                "assignee": row.assignee,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in task_result.scalars().all()
        ],
        "enforcement_log": [
            {
                "id": str(row.id),
                "task_id": str(row.task_id) if row.task_id else None,
                "todoist_task_id": row.todoist_task_id,
                "check_type": row.check_type,
                "has_update": row.has_update,
                "notified_user": row.notified_user,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in enforce_result.scalars().all()
        ],
    }
