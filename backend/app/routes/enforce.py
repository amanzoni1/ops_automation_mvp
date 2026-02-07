from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import models
from app.db.session import get_db
from app.services.audit import log_action
from app.services.enforcement import check_high_priority_tasks
from app.services.n8n_client import post_outbound
from app.services.todoist_client import TodoistClient

router = APIRouter()


def _check_type_for_hour(hour: int) -> str:
    if hour >= 20:
        return "escalation_20"
    if hour >= 18:
        return "escalation_18"
    return "reminder_16"


@router.post("/tasks/enforce")
async def enforce(
    session: AsyncSession = Depends(get_db),
    debug: bool = Query(default=False),
) -> dict:
    if not settings.todoist_api_token:
        raise HTTPException(status_code=400, detail="Todoist API token not configured")

    check_type = _check_type_for_hour(datetime.now().hour)
    todoist_client = TodoistClient(settings.todoist_api_token)
    reminders, checked = await check_high_priority_tasks(session, todoist_client, check_type)

    for reminder in reminders:
        assignee = reminder.assignee
        if isinstance(assignee, str) and assignee.strip().lower() in {"none", "null", ""}:
            assignee = None

        if assignee:
            outbound = {
                "action": "send_slack_dm",
                "user_id": assignee,
                "text": f"⏰ Reminder: Your task '{reminder.title}' is high priority and needs an EOD status update in Todoist comments.",
            }
        elif settings.default_reminder_channel:
            outbound = {
                "action": "send_slack_message",
                "channel": settings.default_reminder_channel,
                "text": f"⏰ Reminder: Task '{reminder.title}' is high priority and needs an EOD status update in Todoist comments.",
            }
        elif settings.default_reminder_user_id:
            outbound = {
                "action": "send_slack_dm",
                "user_id": settings.default_reminder_user_id,
                "text": f"⏰ Reminder: Task '{reminder.title}' is high priority and needs an EOD status update in Todoist comments.",
            }
        else:
            outbound = {
                "action": "send_log",
                "text": f"⏰ Reminder: Task '{reminder.title}' is high priority and needs an EOD status update in Todoist comments.",
            }
        await post_outbound(
            outbound,
            session=session,
        )
        await log_action(
            session,
            actor="system",
            action="reminder_sent",
            details={"todoist_task_id": reminder.todoist_task_id, "user": reminder.assignee},
        )

    response = {
        "checked": checked,
        "reminders_sent": len(reminders),
        "tasks": [
            {
                "task_id": reminder.todoist_task_id,
                "title": reminder.title,
                "assignee": reminder.assignee,
                "reminded": reminder.reminded,
            }
            for reminder in reminders
        ],
    }
    if debug:
        tasks = await todoist_client.get_tasks()
        response["debug_tasks"] = [
            {
                "id": str(getattr(task, "id", "")),
                "content": getattr(task, "content", ""),
                "priority": getattr(task, "priority", None),
                "due": getattr(getattr(task, "due", None), "date", None),
            }
            for task in tasks[:20]
        ]
        result = await session.execute(
            select(models.Task).order_by(models.Task.created_at.desc()).limit(20)
        )
        response["debug_db_tasks"] = [
            {
                "id": str(task.id),
                "todoist_id": task.todoist_id,
                "title": task.title,
                "priority": task.priority,
                "assignee": task.assignee,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "status": task.status,
            }
            for task in result.scalars().all()
        ]
    return response
