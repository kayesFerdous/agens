from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil.parser import parse

from core.tool_interface import Tool
from db.database import async_session
from db.models import ScheduleEvent


def _parse_to_utc(value: str) -> datetime:
    parsed = parse(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone(timezone.utc)


class ScheduleAddTool(Tool):
    @property
    def name(self) -> str:
        return "schedule_add"

    @property
    def description(self) -> str:
        return "Add a calendar, schedule, meeting, event, appointment, or reminder."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title."},
                "start_time": {
                    "type": "string",
                    "description": "Event start time, ISO 8601 or natural-ish format.",
                },
                "end_time": {
                    "type": "string",
                    "description": "Optional event end time, ISO 8601 or natural-ish format.",
                },
                "description": {"type": "string", "description": "Optional event details."},
            },
            "required": ["title", "start_time"],
        }

    async def execute(self, **kwargs: Any) -> dict:
        try:
            start_time = _parse_to_utc(kwargs["start_time"])
            end_time = _parse_to_utc(kwargs["end_time"]) if kwargs.get("end_time") else None
            event = ScheduleEvent(
                title=kwargs["title"],
                start_time=start_time,
                end_time=end_time,
                description=kwargs.get("description"),
            )
            async with async_session() as db:
                db.add(event)
                await db.commit()
                await db.refresh(event)
                return {
                    "status": "created",
                    "event_id": event.id,
                    "title": event.title,
                    "start_time": start_time.isoformat(),
                }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
