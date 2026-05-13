from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil.parser import parse
from sqlalchemy import select

from core.tool_interface import Tool
from db.database import async_session
from db.models import ScheduleEvent


def _parse_to_utc(value: str) -> datetime:
    parsed = parse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(timezone.utc)


class ScheduleUpdateTool(Tool):
    @property
    def name(self) -> str:
        return "schedule_update"

    @property
    def description(self) -> str:
        return "Update or reschedule a calendar, schedule, meeting, event, appointment, or reminder."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "event_id": {"type": "integer", "description": "Event id to update."},
                "title": {"type": "string", "description": "New event title."},
                "start_time": {
                    "type": "string",
                    "description": "New start time, ISO 8601 or natural-ish format.",
                },
                "end_time": {
                    "type": "string",
                    "description": "New end time, ISO 8601 or natural-ish format.",
                },
                "description": {"type": "string", "description": "New event details."},
            },
            "required": ["event_id"],
        }

    async def execute(self, **kwargs: Any) -> dict:
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(ScheduleEvent).where(ScheduleEvent.id == kwargs["event_id"])
                )
                event = result.scalars().first()
                if event is None:
                    return {"status": "not_found"}

                changes: dict[str, Any] = {}
                if "title" in kwargs:
                    event.title = kwargs["title"]
                    changes["title"] = event.title
                if "start_time" in kwargs:
                    event.start_time = _parse_to_utc(kwargs["start_time"])
                    changes["start_time"] = event.start_time.isoformat()
                if "end_time" in kwargs:
                    event.end_time = _parse_to_utc(kwargs["end_time"]) if kwargs["end_time"] else None
                    changes["end_time"] = event.end_time.isoformat() if event.end_time else None
                if "description" in kwargs:
                    event.description = kwargs["description"]
                    changes["description"] = event.description

                await db.commit()
                return {
                    "status": "updated",
                    "event_id": event.id,
                    "changes": changes,
                }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
