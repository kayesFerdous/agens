# llm/client.py
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, APIStatusError, APITimeoutError, APIError

from llm.providers import ProviderConfig
from llm.errors import normalize_error, RateLimitError, LLMUnavailableError
from llm.stream import assemble_stream
from core.types import StreamEvent, ToolCall, Usage

logger = logging.getLogger(__name__)


def _provider_tool_metadata(tool_call: dict) -> dict[str, Any]:
    return {
        key: tool_call[key]
        for key in ("extra_content", "thought_signature", "thoughtSignature")
        if key in tool_call
    }


def _replay_tool_arguments(tool_call: dict) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict) and "_parse_error" in arguments:
        return json.dumps(arguments)
    return tool_call["arguments_raw"]


def _sanitize_tool_call_ids(messages: list[dict]) -> tuple[list[dict], int]:
    """Rewrite every tool_call ID to a unique 'call_N' sequence."""
    result: list[dict] = []
    id_map: dict[str, str] = {}
    counter = 0

    for msg in messages:
        new_msg = dict(msg)

        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            new_tool_calls: list[dict] = []
            for tc in msg["tool_calls"]:
                old_id = tc.get("id")
                if old_id is not None:
                    new_id = f"call_{counter}"
                    counter += 1
                    id_map[old_id] = new_id
                    new_tool_calls.append({**tc, "id": new_id})
                else:
                    new_tool_calls.append(tc)
            new_msg["tool_calls"] = new_tool_calls

        if msg.get("role") == "tool":
            old_tool_id = msg.get("tool_call_id")
            if old_tool_id in id_map:
                new_msg["tool_call_id"] = id_map[old_tool_id]

        result.append(new_msg)

    return result, counter


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
            max_retries=0,
        )

    def swap_key(self, new_config: ProviderConfig) -> None:
        """
        Replace the active provider config and rebuild the OpenAI client.
        Used when rotation moves to a different key, possibly on another provider.
        """
        self.config = new_config
        self._openai = AsyncOpenAI(
            api_key=new_config.api_key,
            base_url=new_config.base_url,
            timeout=new_config.timeout,
            max_retries=0,
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
        usage_accum = Usage()
        # Working message list — we append to it as the conversation progresses.
        working_messages, tool_call_counter = _sanitize_tool_call_ids(list(messages))

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
                        usage = event.get("usage")
                        if isinstance(usage, dict):
                            usage_accum.record(
                                prompt_tokens=usage.get("prompt_tokens", 0) or 0,
                                completion_tokens=usage.get("completion_tokens", 0) or 0,
                                total_tokens=usage.get("total_tokens", 0) or 0,
                            )
                        break

            except APIStatusError as e:
                raise normalize_error(e, provider=self.config.name)
            except APITimeoutError:
                raise LLMUnavailableError(f"Request timed out after {self.config.timeout}s")
            except APIError as e:
                error_msg = str(e).lower()
                if "failed_generation" in error_msg or "failed to call a function" in error_msg:
                    raise LLMUnavailableError(
                        f"{self.config.name} model failed to generate a valid tool call. "
                        "Try a different model or reduce the number of enabled tools."
                    )
                # Base APIError without a status code — wrap it directly, don't call normalize_error
                raise LLMUnavailableError(f"{self.config.name} API error: {e}")

            # ── No tool calls → final answer ─────────────────────────────────────
            if not assembled_tool_calls:
                yield StreamEvent(
                    type="done",
                    tool_calls=tool_history,
                    usage=usage_accum,
                )
                return

            # ── Tool calls present → execute them, loop ───────────────────────────
            # Append the assistant's tool-call turn to working messages.
            remapped_calls: list[dict] = []
            for tc in assembled_tool_calls:
                new_id = tc.get("id") or f"call_{tool_call_counter}"
                if not tc.get("id"):
                    tool_call_counter += 1
                remapped_calls.append({**tc, "id": new_id})

            assistant_tool_calls: list[dict] = []
            for tc in remapped_calls:
                assistant_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": _replay_tool_arguments(tc),
                    },
                    **_provider_tool_metadata(tc),
                })

            assistant_message = {
                "role": "assistant",
                "tool_calls": assistant_tool_calls,
            }
            if text_parts:
                assistant_message["content"] = "".join(text_parts)
            working_messages.append(assistant_message)

            for tc in remapped_calls:
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
                    "name": name,
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
        yield StreamEvent(type="done", tool_calls=tool_history)
