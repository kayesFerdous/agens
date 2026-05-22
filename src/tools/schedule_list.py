from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from dateutil.parser import parse
from sqlalchemy import select

from core.tool_interface import Tool
from db.database import async_session
from db.models import ScheduleEvent


def _utc_to_local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(datetime.now().astimezone().tzinfo)


def _range_bounds(range_name: str) -> tuple[datetime | None, datetime | None]:
    local_tz = datetime.now().astimezone().tzinfo
    now = datetime.now(local_tz)

    if range_name == "all":
        return None, None

    if range_name == "today":
        day = now.date()
    elif range_name == "tomorrow":
        day = now.date() + timedelta(days=1)
    elif range_name == "this_week":
        start_date = now.date() - timedelta(days=now.weekday())
        start = datetime.combine(start_date, time.min, tzinfo=local_tz)
        end = start + timedelta(days=7)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    else:
        day = parse(range_name).date()

    start = datetime.combine(day, time.min, tzinfo=local_tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class ScheduleListTool(Tool):
    @property
    def name(self) -> str:
        return "schedule_list"

    @property
    def description(self) -> str:
        return "List calendar events or reminders in a range."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "Range: 'today', 'tomorrow', 'this_week', 'all', or ISO date YYYY-MM-DD.",
                },
            },
            "required": ["range"],
        }

    async def execute(self, **kwargs: Any) -> dict:
        range_name = kwargs["range"]
        try:
            start, end = _range_bounds(range_name)
            stmt = select(ScheduleEvent).order_by(ScheduleEvent.start_time)
            if start is not None:
                stmt = stmt.where(ScheduleEvent.start_time >= start)
            if end is not None:
                stmt = stmt.where(ScheduleEvent.start_time < end)

            async with async_session() as db:
                result = await db.execute(stmt)
                rows = result.scalars().all()

            events = [
                {
                    "id": event.id,
                    "title": event.title,
                    "start": _utc_to_local(event.start_time).isoformat(),
                    "end": _utc_to_local(event.end_time).isoformat() if event.end_time else None,
                }
                for event in rows
            ]
            if not events:
                return {"events": [], "message": f"No events found for {range_name}."}
            return {"events": events}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
