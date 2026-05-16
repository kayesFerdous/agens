# llm/client.py
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, APIStatusError, APITimeoutError

from llm.providers import ProviderConfig
from llm.errors import normalize_error, RateLimitError, LLMUnavailableError
from llm.stream import assemble_stream
from core.types import StreamEvent, ToolCall

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Single async client for all OpenAI-compatible providers.
    
    Stateless with respect to conversation history — the caller 
    (agent.py) owns the message list. This class only knows how 
    to make one API call and stream the result.
    """

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._openai = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    def swap_key(self, new_api_key: str) -> None:
        """Replace the API key in-place (used by rotation logic)."""
        self.config = ProviderConfig(
            **{**self.config.__dict__, "api_key": new_api_key}
        )
        self._openai = AsyncOpenAI(
            api_key=new_api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    async def react_stream(
        self,
        *,
        messages: list[dict],
        model: str | None = None,
        tool_schemas: list[dict],
        tool_executor: Any,   # Callable[[str, dict], Awaitable[dict]]
        max_iterations: int = 20,
    ) -> AsyncIterator[StreamEvent]:
        """
        Full ReAct loop: stream text, intercept tool calls, execute them,
        loop until a final text answer with no more tool calls.
        
        Yields StreamEvent objects — same types as before, so your 
        interface adapters (web, TUI, Telegram) need zero changes.
        """
        active_model = model or self.config.default_model
        tool_history: list[ToolCall] = []
        # Working message list — we append to it as the conversation progresses.
        working_messages = list(messages)

        for iteration in range(max_iterations):
            logger.debug("ReAct iteration %d, model=%s", iteration + 1, active_model)

            text_parts: list[str] = []
            assembled_tool_calls: list[dict] = []

            try:
                async for event in assemble_stream(
                    client=self._openai,
                    model=active_model,
                    messages=working_messages,
                    tool_schemas=tool_schemas,
                    config=self.config,
                ):
                    if event["type"] == "token":
                        text_parts.append(event["content"])
                        yield StreamEvent(type="token", content=event["content"])

                    elif event["type"] == "tool_call":
                        assembled_tool_calls.append(event["call"])

                    elif event["type"] == "done":
                        finish_reason = event["finish_reason"]
                        break

            except APIStatusError as e:
                raise normalize_error(e, provider=self.config.name)
            except APITimeoutError:
                raise LLMUnavailableError(f"Request timed out after {self.config.timeout}s")

            # ── No tool calls → final answer ─────────────────────────────────────
            if not assembled_tool_calls:
                yield StreamEvent(
                    type="done",
                    tool_calls=tool_history,
                    next_action=None,
                )
                return

            # ── Tool calls present → execute them, loop ───────────────────────────
            # Append the assistant's tool-call turn to working messages.
            working_messages.append({
                "role": "assistant",
                "content": "".join(text_parts) or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments_raw"],
                        },
                    }
                    for tc in assembled_tool_calls
                ],
            })

            for tc in assembled_tool_calls:
                name = tc["name"]
                args = tc["arguments"]  # Already parsed dict

                logger.info("Tool call: %s(%s)", name, args)
                yield StreamEvent(type="tool_start", tool=name, arguments=args)

                call_record = ToolCall(tool=name, arguments=args)
                try:
                    result = await tool_executor(name, args)
                    call_record.result = result
                    yield StreamEvent(type="tool_end", tool=name, result=result)
                except Exception as e:
                    error_str = f"{type(e).__name__}: {e}"
                    result = {"error": error_str}
                    call_record.error = error_str
                    logger.warning("Tool %s failed: %s", name, error_str)
                    yield StreamEvent(type="tool_end", tool=name, error=error_str)

                tool_history.append(call_record)

                # Append tool result to working messages (OpenAI format).
                working_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

        # Max iterations hit — ask for a final answer without tools.
        logger.warning("ReAct max iterations (%d) reached. Requesting final answer.", max_iterations)
        working_messages.append({
            "role": "user",
            "content": "You've reached the iteration limit. Summarize what you found and answer now.",
        })
        async for event in assemble_stream(
            client=self._openai,
            model=active_model,
            messages=working_messages,
            tool_schemas=[],  # No tools → forces text answer
            config=self.config,
        ):
            if event["type"] == "token":
                yield StreamEvent(type="token", content=event["content"])
        yield StreamEvent(type="done", tool_calls=tool_history, next_action=None)