# llm/gemini.py
from __future__ import annotations
from collections.abc import Callable, AsyncIterator, Awaitable
from typing import Any
from google import genai
from google.genai import errors
from google.genai.types import Content, FunctionDeclaration, GenerateContentConfig, Part, Tool

from llm.base import LLM
from llm.gemini_usage import extract_gemini_usage
from core.types import StreamEvent, ToolCall, Usage
from config.logging import get_logger
from config.settings import settings
from llm.llm_exceptions import RateLimitError
from services.api_key_manager import APIKeyManager

logger = get_logger(__name__)

DAILY_KEYWORDS = ("per day", "daily", "quota exceeded", "resource exhausted")
DAY_IN_SECONDS = 86400

def _parse_rate_limit(e: errors.APIError, key_id: str) -> RateLimitError:
    # 1. Try Retry-After header first (most accurate)
    retry_after = None
    if hasattr(e, "response") and e.response is not None:
        raw = e.response.headers.get("Retry-After")
        if raw:
            try:
                retry_after = int(raw)
            except ValueError:
                from email.utils import parsedate_to_datetime
                from datetime import datetime, timezone
                dt = parsedate_to_datetime(raw)
                retry_after = int((dt - datetime.now(timezone.utc)).total_seconds())

    # 2. Fall back to message parsing (Gemini's typical behavior)
    error_msg = str(e).lower()
    is_daily = any(kw in error_msg for kw in DAILY_KEYWORDS)

    if retry_after is None:
        retry_after = DAY_IN_SECONDS if is_daily else None  # short limit: let manager decide

    return RateLimitError(key_id=key_id, retry_after=retry_after, is_daily=is_daily)


class GeminiLLM(LLM):
    """Google Gemini backend implementing all generation modes."""

    def __init__(
        self,
        usage: Usage,
        client: genai.Client,
        current_key_id: str | None = None,
    ) -> None:
        self.usage = usage
        self._provider = "google"
        self._client: genai.Client | None = client
        self._current_key_id = current_key_id or ""
        self._model = settings.DEFAULT_MODEL


    async def react_stream(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 10,
        temperature: float = 0,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming variant of react(). Yields StreamEvent objects in real time."""
        message_history = message_history or []

        func_decls = [
            FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in tool_schemas
        ]
        tools = [Tool(function_declarations=func_decls)]

        config = GenerateContentConfig(
            system_instruction=system or None,
            tools=tools,
            temperature=temperature,
        )

        contents: list[Content] = message_history + [
            Content(role="user", parts=[Part.from_text(text=user_request)])
        ]

        tool_history: list[ToolCall] = []
        truncated_indices: set[int] = set()

        for iteration in range(max_iterations):
            logger.info("ReAct stream iteration %d", iteration + 1)
            self._reduce_tool_outputs(contents, truncated_indices)

            # Use non-streaming to check if the model wants tools or text
            client = self._require_client()
            try:
                response = await client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
            except errors.APIError as e:
                if e.code == 429:
                    raise _parse_rate_limit(e, self._current_key_id or "unknown")
                if e.code == 503:
                    raise RateLimitError(key_id=self._current_key_id, retry_after=60, is_daily=False)
                raise

            extract_gemini_usage(response, self.usage, logger=logger)

            if not response.candidates:
                yield StreamEvent(type="error", error="Gemini returned no candidates.")
                return

            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                reason = getattr(candidate, "finish_reason", "UNKNOWN")
                yield StreamEvent(type="error", error=f"No content. Finish reason: {reason}")
                return

            content_parts = candidate.content.parts
            function_calls = [p for p in content_parts if p.function_call]

            # --- Final text answer: re-request with streaming ---
            if not function_calls:
                self.usage.log(logger, model=self._model, context="react_stream")
                logger.info("ReAct stream: final answer at iteration %d — streaming text", iteration + 1)

                # Stream the final answer using generate_content_stream
                stream_config = GenerateContentConfig(
                    system_instruction=system or None,
                    temperature=temperature,
                    # No tools — force a text-only response
                )

                try:
                    client = self._require_client()
                    async for chunk in await client.aio.models.generate_content_stream(
                        model=self._model,
                        contents=contents,
                        config=stream_config,
                    ):
                        if chunk.text:
                            yield StreamEvent(type="token", content=chunk.text)
                        # Capture usage from the last chunk
                        if chunk.usage_metadata:
                            self.usage.record(
                                prompt_tokens=chunk.usage_metadata.prompt_token_count or 0,
                                completion_tokens=getattr(chunk.usage_metadata, "candidates_token_count", None) or 0,
                                total_tokens=chunk.usage_metadata.total_token_count or 0,
                            )

                    yield StreamEvent(type="done", usage=self.usage, tool_calls=tool_history)
                    return
                except errors.APIError as e:
                    if e.code == 429:
                        raise _parse_rate_limit(e, self._current_key_id or "unknown")
                    if e.code == 503:
                        raise RateLimitError(key_id=self._current_key_id, retry_after=60, is_daily=False)
                    raise

            # --- Tool-calling iteration ---
            contents.append(candidate.content)

            func_response_parts: list[Part] = []
            for part in function_calls:
                fc = part.function_call
                if not fc or not fc.name:
                    continue

                fc_name = fc.name
                fc_args = dict(fc.args) if fc.args else {}

                logger.info("Tool call (stream): %s(%s)", fc_name, fc_args)
                yield StreamEvent(type="tool_start", tool=fc_name, arguments=fc_args)

                call_record = ToolCall(tool=fc_name, arguments=fc_args)

                try:
                    result = await tool_executor(fc_name, fc_args)
                    call_record.result = result
                    logger.info("Tool result (stream): %s", str(result)[:200])
                    yield StreamEvent(type="tool_end", tool=fc_name, result=result)
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    result = {"error": error_msg}
                    call_record.error = error_msg
                    logger.warning("Tool error (stream): %s", error_msg)
                    yield StreamEvent(type="tool_end", tool=fc_name, error=error_msg)

                tool_history.append(call_record)
                func_response_parts.append(
                    Part.from_function_response(name=fc_name, response=result)
                )

            contents.append(Content(role="tool", parts=func_response_parts))

        # --- Max iterations exhausted: stream fallback answer ---
        logger.warning("ReAct stream hit max iterations (%d). Requesting final answer.", max_iterations)
        contents.append(
            Content(
                role="user",
                parts=[Part.from_text(
                    text="You have used all available iterations. Provide your best answer now based on the information gathered so far."
                )],
            )
        )
        fallback_config = GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )

        try:
            client = self._require_client()
            async for chunk in await client.aio.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=fallback_config,
            ):
                if chunk.text:
                    yield StreamEvent(type="token", content=chunk.text)

            self.usage.log(logger, model=self._model, context="react_stream_fallback")
            yield StreamEvent(type="done", usage=self.usage, tool_calls=tool_history)
        except errors.APIError as e:
            if e.code == 429:
                raise _parse_rate_limit(e, self._current_key_id or "unknown")
            if e.code == 503:
                raise RateLimitError(key_id=self._current_key_id, retry_after=60, is_daily=False)
            raise

    def _reduce_tool_outputs(self, contents: list[Content], truncated_indices: set[int], max_chars: int = 500) -> None:
        """Truncate old tool outputs to reduce token usage, keeping the last output intact."""
        for i, content in enumerate(contents[:-1]):
            if i in truncated_indices or content.role != "tool" or not content.parts:
                continue

            new_parts = []
            for part in content.parts:
                if part.function_response and part.function_response.response:
                    response = part.function_response.response
                    response_name = part.function_response.name or "unknown_tool"
                    truncated_response = {
                        key: value[:max_chars] + "... [truncated]"
                        if isinstance(value, str) and len(value) > max_chars
                        else value
                        for key, value in response.items()
                    }
                    new_parts.append(
                        Part.from_function_response(
                            name=response_name,
                            response=truncated_response,
                        )
                    )
                else:
                    new_parts.append(part)

            contents[i] = Content(role="tool", parts=new_parts)
            truncated_indices.add(i)


    async def rotate_key(self, api_key_manager: APIKeyManager) -> None:
        """Invalidate current client so next _get_client() picks a fresh key."""
        self._client = None
        key, raw_key = await api_key_manager.get_key_for_use(self._provider)
        self._current_key_id = key.id
        self._client = genai.Client(api_key=raw_key)


    # ----- shared helper -----

    def _require_client(self) -> genai.Client:
        if self._client is None:
            raise RuntimeError("Gemini client is not initialized")
        return self._client

    async def _call(self, prompt: str, config: GenerateContentConfig) -> str:
        client = self._require_client()
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

        extract_gemini_usage(response, self.usage, logger=logger)
        self.usage.log(logger, model=self._model, context="generate")

        if response.text is None:
            raise RuntimeError("Gemini returned empty response")
        return response.text
