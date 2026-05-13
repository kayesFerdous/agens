from __future__ import annotations

from typing import Any

from sqlalchemy import select

from core.tool_interface import Tool
from db.database import async_session
from db.models import ScheduleEvent


class ScheduleDeleteTool(Tool):
    @property
    def name(self) -> str:
        return "schedule_delete"

    @property
    def description(self) -> str:
        return "Delete or cancel a calendar, schedule, meeting, event, appointment, or reminder by id or title match."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "event_id": {"type": "integer", "description": "Event id to delete."},
                "title": {
                    "type": "string",
                    "description": "Title text to fuzzy-match when event_id is not provided.",
                },
            },
        }

    async def execute(self, **kwargs: Any) -> dict:
        try:
            async with async_session() as db:
                stmt = select(ScheduleEvent)
                if kwargs.get("event_id") is not None:
                    stmt = stmt.where(ScheduleEvent.id == kwargs["event_id"])
                elif kwargs.get("title"):
                    stmt = stmt.where(ScheduleEvent.title.ilike(f"%{kwargs['title']}%"))
                    stmt = stmt.order_by(ScheduleEvent.start_time)
                else:
                    return {"status": "not_found"}

                result = await db.execute(stmt)
                event = result.scalars().first()
                if event is None:
                    return {"status": "not_found"}

                event_id = event.id
                title = event.title
                await db.delete(event)
                await db.commit()
                return {"status": "deleted", "event_id": event_id, "title": title}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
