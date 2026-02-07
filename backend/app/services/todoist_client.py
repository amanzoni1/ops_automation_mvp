import asyncio
from typing import Any, Iterable

from todoist_api_python.api import TodoistAPI


class TodoistClient:
    def __init__(self, api_token: str) -> None:
        self.api = TodoistAPI(api_token)

    async def add_task(
        self,
        content: str,
        priority: int | None = None,
        due_string: str | None = None,
        labels: Iterable[str] | None = None,
        description: str | None = None,
    ) -> Any:
        def _call() -> Any:
            return self.api.add_task(
                content=content,
                priority=priority,
                due_string=due_string,
                labels=list(labels) if labels else None,
                description=description,
            )

        return await asyncio.to_thread(_call)

    async def add_comment(self, task_id: str, content: str) -> Any:
        def _call() -> Any:
            return self.api.add_comment(task_id=task_id, content=content)

        return await asyncio.to_thread(_call)

    async def get_tasks(self, filter_query: str | None = None) -> list[Any]:
        def _call() -> list[Any]:
            return self.api.get_tasks(filter=filter_query)

        return await asyncio.to_thread(_call)

    async def get_comments(self, task_id: str) -> list[Any]:
        def _call() -> list[Any]:
            return self.api.get_comments(task_id=task_id)

        return await asyncio.to_thread(_call)
