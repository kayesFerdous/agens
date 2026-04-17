from google.genai.types import Content, Part
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

    async def get_history_for_gemini(self, session_id: str, max_history: int = 3) -> list[Content]:
        messages = await self.get_history(session_id, max_history)

        return [
            Content(
                role="user" if msg.role == "user" else "model",
                parts=[Part.from_text(text=msg.content)]
            )
            for msg in messages
        ]
