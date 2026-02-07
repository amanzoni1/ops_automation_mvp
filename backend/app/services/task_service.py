import logging
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.services.audit import log_action

logger = logging.getLogger(__name__)


def _parse_due_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


async def create_task_with_enrichment(
    session: AsyncSession,
    todoist_client: Any,
    extracted_fields: dict[str, Any],
    enrichment_tips: str,
    inbox_event_id: str | None,
    task_type: str | None,
) -> models.Task:
    title = extracted_fields.get("title") or "Untitled task"
    priority = extracted_fields.get("priority")
    due_date = extracted_fields.get("due_date")
    labels = extracted_fields.get("labels") or []
    description = extracted_fields.get("description") or ""

    try:
        task = await todoist_client.add_task(
            content=title,
            priority=priority,
            due_string=due_date,
            labels=labels,
            description=description,
        )
    except TypeError:
        task = await todoist_client.add_task(
            content=title,
            priority=priority,
            due_string=due_date,
            labels=labels,
        )
    except Exception as exc:
        logger.exception("Todoist task creation failed", exc_info=exc)
        await log_action(
            session,
            actor="system",
            action="task_create_failed",
            details={"error": str(exc)},
        )
        raise

    try:
        await todoist_client.add_comment(
            task_id=str(task.id),
            content=(
                "📋 SOP Reminders for this task:\n"
                f"{enrichment_tips}\n\n---\n"
                "Auto-generated from company SOPs."
            ),
        )
        enrichment_added = True
    except Exception as exc:
        logger.exception("Todoist comment failed", exc_info=exc)
        enrichment_added = False

    assignee_id = getattr(task, "assignee_id", None)
    assignee = str(assignee_id) if assignee_id not in (None, "") else None
    if isinstance(assignee, str) and assignee.strip().lower() in {"none", "null", ""}:
        assignee = None
    if not assignee:
        assignee = extracted_fields.get("assignee")
    if isinstance(assignee, str) and assignee.strip().lower() in {"none", "null", ""}:
        assignee = None
    logger.info("Task assignee resolved", extra={"assignee": assignee, "todoist_id": str(task.id)})

    record = models.Task(
        todoist_id=str(task.id),
        title=title,
        task_type=task_type,
        priority=priority,
        assignee=assignee,
        due_date=_parse_due_date(due_date),
        enrichment_added=enrichment_added,
        sops_cited=None,
        inbox_event_id=inbox_event_id,
    )
    session.add(record)
    await session.commit()

    await log_action(
        session,
        actor="system",
        action="task_created",
        entity_type="task",
        entity_id=record.id,
        details={"todoist_id": str(task.id), "enrichment_added": enrichment_added},
    )
    return record
