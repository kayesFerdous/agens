from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message
from db.repository import add_message, get_messages


class MemoryManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        tool_calls: list[dict] | None = None
    ) -> None:
        await add_message(self.db, session_id, "user", user_msg)
        await add_message(self.db, session_id, "assistant", assistant_msg, tool_calls)

    async def get_history(self, session_id: str, max_history: int = 3) -> list[Message]:
        return await get_messages(self.db, session_id, max_history)

    async def get_history_as_openai_messages(self, session_id: str, max_history: int = 3) -> list[dict]:
        """
        Return conversation history as OpenAI-format message dicts.
        Used by LLMClient instead of the Gemini Content format.
        """
        messages = await self.get_history(session_id, max_history)
        result: list[dict] = []

        for msg in messages:
            if msg.role == "user":
                result.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    import json

                    try:
                        tool_calls_data = (
                            msg.tool_calls
                            if isinstance(msg.tool_calls, list)
                            else json.loads(msg.tool_calls)
                        )
                        tool_calls = []
                        for i, tc in enumerate(tool_calls_data):
                            if not isinstance(tc, dict) or "tool" not in tc:
                                continue
                            tool_calls.append({
                                "id": tc.get("id", f"call_{i}"),
                                "type": "function",
                                "function": {
                                    "name": tc["tool"],
                                    "arguments": json.dumps(tc.get("arguments", {})),
                                },
                            })
                        if tool_calls:
                            entry["tool_calls"] = tool_calls
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
                result.append(entry)

        return result
