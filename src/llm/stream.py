# llm/stream.py
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ThinkingStripper:
    """
    Stateful stripper that removes <think>...</think> and
    <thinking>...</thinking> blocks from a streaming token sequence.
    """

    _OPEN_TAGS = ("<think>", "<thinking>", "<thought>")
    _CLOSE_TAGS = ("</think>", "</thinking>", "</thought>")
    _MAX_BUFFER = 24

    def __init__(self) -> None:
        self._in_think: bool = False
        self._buffer: str = ""

    def feed(self, chunk: str) -> str:
        """Process one raw chunk and return clean text to emit."""
        self._buffer += chunk
        output: list[str] = []

        while self._buffer:
            if self._in_think:
                closed, remainder = self._find_close_tag(self._buffer)
                if closed:
                    self._buffer = remainder
                    self._in_think = False
                else:
                    safe_to_discard = self._safe_discard_length(
                        self._buffer, self._CLOSE_TAGS
                    )
                    self._buffer = self._buffer[safe_to_discard:]
                    break
            else:
                opened, before, remainder = self._find_open_tag(self._buffer)
                if opened:
                    output.append(before)
                    self._buffer = remainder
                    self._in_think = True
                else:
                    safe_len = self._safe_emit_length(self._buffer, self._OPEN_TAGS)
                    output.append(self._buffer[:safe_len])
                    self._buffer = self._buffer[safe_len:]
                    break

        return "".join(output)

    def flush(self) -> str:
        """Emit remaining non-thinking buffered content after the stream ends."""
        if self._in_think:
            self._buffer = ""
            return ""
        result = self._buffer
        self._buffer = ""
        return result

    def _find_open_tag(self, text: str) -> tuple[bool, str, str]:
        """Return (found, text_before_tag, text_after_tag)."""
        lowered = text.lower()
        earliest_pos = len(text)
        earliest_tag_len = 0
        for tag in self._OPEN_TAGS:
            idx = lowered.find(tag)
            if idx != -1 and idx < earliest_pos:
                earliest_pos = idx
                earliest_tag_len = len(tag)
        if earliest_tag_len:
            return True, text[:earliest_pos], text[earliest_pos + earliest_tag_len:]
        return False, "", ""

    def _find_close_tag(self, text: str) -> tuple[bool, str]:
        """Return (found, text_after_tag)."""
        lowered = text.lower()
        earliest_pos = len(text)
        earliest_tag_len = 0
        for tag in self._CLOSE_TAGS:
            idx = lowered.find(tag)
            if idx != -1 and idx < earliest_pos:
                earliest_pos = idx
                earliest_tag_len = len(tag)
        if earliest_tag_len:
            return True, text[earliest_pos + earliest_tag_len:]
        return False, ""

    def _safe_emit_length(self, text: str, tags: tuple[str, ...]) -> int:
        """
        How many leading characters are safe to emit while preserving any
        possible partial tag at the tail.
        """
        max_tag_len = max(len(t) for t in tags)
        if len(text) <= max_tag_len:
            return 0
        tail_start = len(text) - max_tag_len
        lowered = text.lower()
        for tag in tags:
            for start in range(tail_start, len(text)):
                if tag.startswith(lowered[start:]):
                    return start
        return len(text) - max_tag_len

    def _safe_discard_length(self, text: str, tags: tuple[str, ...]) -> int:
        """
        How many leading characters are safe to discard while preserving any
        possible partial closing tag at the tail.
        """
        max_tag_len = max(len(t) for t in tags)
        if len(text) <= max_tag_len:
            return 0
        tail_start = len(text) - max_tag_len
        lowered = text.lower()
        for tag in tags:
            for start in range(tail_start, len(text)):
                if tag.startswith(lowered[start:]):
                    return start
        return len(text) - max_tag_len


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


def _extract_provider_tool_metadata(tool_call_delta: Any) -> dict[str, Any]:
    """
    Return provider-specific tool-call metadata that must be replayed.

    Gemini's OpenAI-compatible API sends function-call thought signatures under
    tool_calls[].extra_content.google.thought_signature. The OpenAI SDK keeps
    unknown response fields in the Pydantic model dump/model_extra, so preserve
    those fields instead of reconstructing a purely OpenAI-standard tool call.
    """
    metadata: dict[str, Any] = {}

    try:
        dumped = tool_call_delta.model_dump(exclude_none=True)
    except AttributeError:
        dumped = {}

    if isinstance(dumped, dict):
        extra_content = dumped.get("extra_content")
        if isinstance(extra_content, dict):
            metadata["extra_content"] = extra_content

        for key in ("thought_signature", "thoughtSignature"):
            value = dumped.get(key)
            if value:
                metadata[key] = value

    model_extra = getattr(tool_call_delta, "model_extra", None)
    if isinstance(model_extra, dict):
        extra_content = model_extra.get("extra_content")
        if isinstance(extra_content, dict):
            metadata["extra_content"] = extra_content

        for key in ("thought_signature", "thoughtSignature"):
            value = model_extra.get(key)
            if value:
                metadata[key] = value

    return metadata


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

    # Request token usage in the final stream chunk when supported.
    kwargs["stream_options"] = {"include_usage": True}

    if tool_schemas:
        kwargs["tools"] = _build_tools_param(tool_schemas)
        # Some providers need this explicitly set; others ignore it.
        if config.force_tool_choice:
            kwargs["tool_choice"] = "auto"
        # Disable parallel tool calls for providers that don't handle it well.
        if config.name == "gemini" or not config.parallel_tool_calls:
            kwargs["parallel_tool_calls"] = False

    # Accumulator for in-progress tool calls, keyed by stream index or provider id.
    # Structure: {key: {"id": str, "name": str, "arguments_raw": str, ...metadata}}
    pending_tool_calls: dict[Any, dict] = {}
    finish_reason: str | None = None
    usage: dict | None = None
    stripper = ThinkingStripper()

    async with await client.chat.completions.create(**kwargs) as stream:
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            if getattr(chunk, "usage", None):
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            delta = choice.delta
            finish_reason = choice.finish_reason or finish_reason

            # ── Text token ───────────────────────────────────────────────────
            if delta.content:
                clean = stripper.feed(delta.content)
                if clean:
                    yield {"type": "token", "content": clean}

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                pass

            # ── Tool call fragment ───────────────────────────────────────────
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    key = (
                        tc_delta.id
                        if config.name == "gemini" and tc_delta.id
                        else tc_delta.index
                    )
                    if key not in pending_tool_calls:
                        pending_tool_calls[key] = {"id": "", "name": "", "arguments_raw": ""}

                    acc = pending_tool_calls[key]
                    acc.update(_extract_provider_tool_metadata(tc_delta))
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            name_part = tc_delta.function.name
                            if not acc["name"]:
                                acc["name"] = name_part
                            elif not acc["name"].endswith(name_part):
                                acc["name"] += name_part
                        if tc_delta.function.arguments:
                            acc["arguments_raw"] += tc_delta.function.arguments

    remainder = stripper.flush()
    if remainder.strip():
        yield {"type": "token", "content": remainder}

    # Stream closed — emit assembled tool calls.
    for acc in pending_tool_calls.values():
        args = _safe_parse_args(acc["arguments_raw"], acc["name"])
        provider_metadata = {
            key: acc[key]
            for key in ("extra_content", "thought_signature", "thoughtSignature")
            if key in acc
        }
        yield {
            "type": "tool_call",
            "call": {
                "id": acc["id"],
                "name": acc["name"],
                "arguments": args,
                "arguments_raw": acc["arguments_raw"],
                **provider_metadata,
            },
        }

    yield {
        "type": "done",
        "finish_reason": finish_reason or "stop",
        "usage": usage,
    }
