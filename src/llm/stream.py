# llm/stream.py
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _build_tools_param(tool_schemas: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["parameters"],
            },
        }
        for s in tool_schemas
    ]


def _safe_parse_args(raw: str, tool_name: str) -> dict:
    """
    Parse tool call arguments JSON. On failure, try light recovery 
    before giving up. Returns a dict always — never raises.
    """
    raw = raw.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt 1: strip trailing commas (a common LLM mistake).
        import re
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Give up — return raw string so the tool can surface the error.
        logger.warning("Could not parse tool args for %s: %r", tool_name, raw[:200])
        return {"_parse_error": raw}


async def assemble_stream(
    *,
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    tool_schemas: list[dict],
    config: Any,  # ProviderConfig
) -> AsyncIterator[dict]:
    """
    Wraps the OpenAI streaming API and yields normalized events:
    
      {"type": "token", "content": str}
      {"type": "tool_call", "call": {...}}
      {"type": "done", "finish_reason": str}
    
    Assembles fragmented tool call arguments before yielding them.
    This is an internal helper — LLMClient.react_stream() calls this.
    """
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    if tool_schemas:
        kwargs["tools"] = _build_tools_param(tool_schemas)
        # Some providers need this explicitly set; others ignore it.
        if config.force_tool_choice:
            kwargs["tool_choice"] = "auto"
        # Disable parallel tool calls for providers that don't handle it well.
        if not config.parallel_tool_calls:
            kwargs["parallel_tool_calls"] = False

    # Accumulator for in-progress tool calls, keyed by stream index.
    # Structure: {index: {"id": str, "name": str, "arguments_raw": str}}
    pending_tool_calls: dict[int, dict] = {}
    finish_reason: str | None = None

    async with await client.chat.completions.create(**kwargs) as stream:
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta
            finish_reason = choice.finish_reason or finish_reason

            # ── Text token ───────────────────────────────────────────────────
            if delta.content:
                yield {"type": "token", "content": delta.content}

            # ── Tool call fragment ───────────────────────────────────────────
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {"id": "", "name": "", "arguments_raw": ""}

                    acc = pending_tool_calls[idx]
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            acc["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            acc["arguments_raw"] += tc_delta.function.arguments

    # Stream closed — emit assembled tool calls.
    for acc in pending_tool_calls.values():
        args = _safe_parse_args(acc["arguments_raw"], acc["name"])
        yield {
            "type": "tool_call",
            "call": {
                "id": acc["id"],
                "name": acc["name"],
                "arguments": args,
                "arguments_raw": acc["arguments_raw"],
            },
        }

    yield {"type": "done", "finish_reason": finish_reason or "stop"}