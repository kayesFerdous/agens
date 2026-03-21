from google.genai.types import Content, Part
from core.types import ConversationTurn

class MemoryManager:
    def __init__(self, max_history: int = 4):
        self._history: list[ConversationTurn] = []
        self.max_history = max_history

    def store(self, user_message: str, assistant_message: str):
        turn = ConversationTurn(user_message, assistant_message)
        self._history.append(turn)

        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

    def get_history_for_gemini(self) -> list[Content]:
        """Convert domain history to Gemini format."""
        contents: list[Content] = []
        for turn in self._history:
            contents.append(
                Content(role="user", parts=[Part.from_text(text=turn.user_message)])
            )
            contents.append(
                Content(role="model", parts=[Part.from_text(text=turn.assistant_message)])
            )
        return contents

    
