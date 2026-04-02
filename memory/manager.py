from google.genai.types import Content, Part
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message
from db.repository import add_message, get_messages


class MemoryManager:
    def __init__(self, db: AsyncSession, session_id: str, max_history: int = 4):
        self.db = db
        self.session_id = session_id
        self.max_history = max_history
        self._cache: list[Message] = []
        self._loaded = False

    async def _ensure_loaded(self, session_id: str):
        if not self._loaded:
            messages = await get_messages(self.db, session_id)
            self._cache = messages[-(self.max_history * 2):]
            self._loaded = True

    async def store(
        self,
        user_msg: str,
        assistant_msg: str,
        tool_calls: list[dict] | None = None
    ) -> None:
        await self._ensure_loaded(self.session_id)

        user_message = await add_message(self.db, self.session_id, "user", user_msg)
        assistant_message = await add_message(self.db, self.session_id, "assistant", assistant_msg, tool_calls)

        self._cache.extend([user_message, assistant_message])
        if len(self._cache) > self.max_history * 2:
            self._cache = self._cache[-(self.max_history * 2):]

    async def get_history_for_gemini(self) -> list[Content]:
        await self._ensure_loaded(self.session_id)

        return [
            Content(
                role="user" if msg.role == "user" else "model",
                parts=[Part.from_text(text=msg.content)]
            )
            for msg in self._cache
        ]
