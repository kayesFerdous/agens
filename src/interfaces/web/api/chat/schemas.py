from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str | None = None
    model: str | None = None
    tool_groups: dict[str, bool] | None = None
    message: str


class UsageResponse(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCallResponse(BaseModel):
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    success: bool
    answer: str | None = None
    tool_history: list[ToolCallResponse] = []
    usage: UsageResponse | None = None
    error: str | None = None
