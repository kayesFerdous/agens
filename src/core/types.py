# core/types.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, TYPE_CHECKING

CONFIRMATION_TTL_SECONDS: int = 300      # 5 minutes
SUDO_AUTHORIZATION_TTL_SECONDS: int = 300  # 5 minutes, single-use per sudo command

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    """Provider-agnostic token usage accumulator.

    Each provider is responsible for extracting counts from its own
    response type and calling ``record()`` with plain ints.
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens

    def log(self, logger: logging.Logger, *, model: str = "", context: str = "") -> None:
        logger.info(
            "token_usage model=%s context=%s prompt=%d completion=%d total=%d",
            model,
            context,
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )


@dataclass
class ToolCall:
    """A single tool invocation recorded during the ReAct loop."""
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class PendingConfirmation:
    """A dangerous action awaiting explicit user approval.

    Stored in-memory on the Agent, keyed by session_id.
    Expires after CONFIRMATION_TTL_SECONDS.
    The LLM is never involved in the approval decision.
    """
    tool_name: str
    arguments: dict[str, Any]
    reason: str            # Why this command is considered dangerous
    command_preview: str   # Human-readable preview of exactly what will run
    created_at: float      # time.time() snapshot — used for TTL checks
    session_id: str
    requires_sudo_auth: bool = False  # True when safety mode is OFF and command needs sudo


@dataclass
class AgentResponse:
    success: bool
    answer: str | None = None
    tool_history: list[ToolCall] = field(default_factory=list)
    error: str | None = None
    usage: Usage | None = None


@dataclass
class StreamEvent:
    """A single event yielded during a streaming ReAct loop.

    Event types:
        tool_start — a tool is about to be executed
        tool_end   — a tool finished (with result or error)
        token      — a chunk of the final text answer
        status     — a non-error lifecycle update for the UI
        error      — an unrecoverable error occurred
        done       — the stream is complete (carries usage + tool history)
    """
    type: Literal[
        "tool_start", "tool_end", "token", "status", "error", "done",
        "confirmation_required",  # agent is paused, waiting for user YES/NO
        "confirmation_result",    # confirmed command finished (or was cancelled)
        "sudo_auth_required",     # YES received but session lacks sudo authorization
    ]

    # token events
    content: str | None = None

    # status events
    message: str | None = None

    # tool events
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    # done event
    usage: Usage | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    # confirmation_required event
    confirmation_reason: str | None = None
    confirmation_preview: str | None = None

    # explicit frontend transition hint (e.g. "await_confirmation", "await_sudo_auth")
    next_action: str | None = None

