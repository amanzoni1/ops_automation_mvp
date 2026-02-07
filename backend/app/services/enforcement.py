from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import models


@dataclass
class Reminder:
    todoist_task_id: str
    title: str
    assignee: str | None
    reminded: bool


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _has_user_update_today(comments: list[Any]) -> bool:
    today = datetime.now(timezone.utc).date()
    for comment in comments:
        content = (getattr(comment, "content", "") or "").strip()
        if content.startswith("📋 SOP Reminders") or "Auto-generated from company SOPs." in content:
            continue
        posted_at = _parse_ts(getattr(comment, "posted_at", None))
        if posted_at and posted_at.date() == today:
            return True
    return False


def _is_due_today_or_overdue(task: Any) -> bool:
    due = getattr(task, "due", None)
    if not due:
        return False
    due_date = getattr(due, "date", None)
    if due_date:
        try:
            parsed = date.fromisoformat(due_date)
        except ValueError:
            return False
        return parsed <= datetime.now(timezone.utc).date()
    return False


async def check_high_priority_tasks(
    session: AsyncSession,
    todoist_client: Any,
    check_type: str,
) -> tuple[list[Reminder], int]:
    today = datetime.now(timezone.utc).date()
    result = await session.execute(
        select(models.Task).where(
            models.Task.status == "open",
            models.Task.priority >= 3,
            models.Task.due_date <= today,
        )
    )
    db_tasks = result.scalars().all()
    reminders: list[Reminder] = []
    checked = 0
    for task in db_tasks:
        checked += 1
        if not task.todoist_id:
            continue
        comments = await todoist_client.get_comments(task.todoist_id)
        if _has_user_update_today(comments):
            continue

        reminder = Reminder(
            todoist_task_id=task.todoist_id,
            title=task.title,
            assignee=task.assignee,
            reminded=True,
        )
        reminders.append(reminder)

        log = models.EnforcementLog(
            task_id=task.id,
            todoist_task_id=task.todoist_id,
            check_type=check_type,
            has_update=False,
            notified_user=reminder.assignee,
        )
        session.add(log)

    await session.commit()
    return reminders, checked
