# llm/gemini.py
from __future__ import annotations
from collections.abc import Callable, AsyncGenerator, AsyncIterator, Awaitable
from typing import Any
from google import genai
from google.genai import errors
from google.genai.types import Content, FunctionDeclaration, GenerateContentConfig, Part, Tool
from sqlalchemy.ext.asyncio import AsyncSession

from llm.base import LLM
from llm.gemini_usage import extract_gemini_usage
from core.types import StreamEvent, ToolCall, Usage
from config.logging import get_logger
from config.settings import settings
from llm.llm_exceptions import RateLimitError, LLMUnavailable
from services.api_key_manager import APIKeyManager
from db.repositories.api_key import APIKeyRepository

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

    # 2. Try retryDelay from the JSON response body
    if retry_after is None:
        retry_after = _extract_retry_delay(e)

    # 3. Fall back to message parsing (Gemini's typical behavior)
    error_msg = str(e).lower()
    is_daily = any(kw in error_msg for kw in DAILY_KEYWORDS)

    if retry_after is None:
        retry_after = DAY_IN_SECONDS if is_daily else 60

    return RateLimitError(key_id=key_id, retry_after=retry_after, is_daily=is_daily)


def _extract_retry_delay(e: errors.APIError) -> int | None:
    """Parse the retryDelay field from a Gemini error response body.

    Gemini returns errors like:
      {"error": {"details": [{"retryDelay": "30s", ...}]}}
    The delay string is typically in the form "<N>s".
    Returns the delay in seconds, or None if not found.
    """
    import json, re

    if not hasattr(e, "response") or e.response is None:
        return None
    try:
        body = e.response.text if hasattr(e.response, "text") else None
        if not body:
            return None
        data = json.loads(body)
        details = data.get("error", {}).get("details", [])
        for detail in details:
            raw_delay = detail.get("retryDelay")
            if raw_delay:
                match = re.match(r"(\d+)", str(raw_delay))
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return None


class GeminiLLM(LLM):
    """Google Gemini backend implementing all generation modes."""

    def __init__(
        self,
        usage: Usage,
        client: genai.Client,
        current_key_id: str | None = None,
        model_name: str | None = None
    ) -> None:
        self.usage = usage
        self._provider = "gemini"
        self._client: genai.Client | None = client
        self._current_key_id = current_key_id or ""
        resolved_model = model_name or settings.DEFAULT_MODEL
        if not resolved_model:
            raise LLMUnavailable("Gemini model is not configured")
        self._model_name: str = resolved_model

    @property
    def current_key_id(self):
        return self._current_key_id

    @property
    def model_name(self):
        return self._model_name


    async def react(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 10,
        temperature: float = 0,
    ) -> str:
        """Non-streaming ReAct loop. Returns the final text response."""
        final_text: list[str] = []

        async for event in self._run_react_loop(
            user_request=user_request,
            system=system,
            tool_schemas=tool_schemas,
            message_history=message_history,
            tool_executor=tool_executor,
            max_iterations=max_iterations,
            temperature=temperature,
            streaming=False,
        ):
            if event.type == "token" and event.content:
                final_text.append(event.content)
            elif event.type == "error":
                raise RuntimeError(event.error or "Unknown ReAct error")

        return "".join(final_text)

    async def react_stream(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 20,
        temperature: float = 0,
        model_name: str | None = None,
        streaming: bool = True,
    ) -> AsyncIterator[StreamEvent]:
        """ReAct event loop. Can stream final text or emit it once when complete."""
        if model_name:
            self._model_name = model_name

        async for event in self._run_react_loop(
            user_request=user_request,
            system=system,
            tool_schemas=tool_schemas,
            message_history=message_history,
            tool_executor=tool_executor,
            max_iterations=max_iterations,
            temperature=temperature,
            streaming=streaming,
        ):
            yield event

    async def _run_react_loop(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 20,
        temperature: float = 0,
        streaming: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Shared ReAct loop used by both react() and react_stream().

        When *streaming* is True the final answer is returned token-by-token via
        generate_content_stream; when False a single generate_content call is
        used so the caller receives all tokens at once (still as StreamEvent
        objects for a uniform interface).
        """
        message_history = message_history or []

        func_decls = [
            FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in tool_schemas
        ]
        tools = [Tool(function_declarations=func_decls)] if func_decls else None

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
            logger.info("ReAct iteration %d (streaming=%s)", iteration + 1, streaming)
            self._reduce_tool_outputs(contents, truncated_indices)

            client = self._require_client()
            try:
                logger.info("api key id: %s", self._current_key_id)
                response = await client.aio.models.generate_content(
                    model=self._model_name,
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

            # --- Final answer (no more tool calls) ---
            if not function_calls:
                self.usage.log(logger, model=self._model_name, context="react_stream" if streaming else "react")
                logger.info("ReAct: final answer at iteration %d (streaming=%s)", iteration + 1, streaming)

                final_config = GenerateContentConfig(
                    system_instruction=system or None,
                    temperature=temperature,
                    # No tools — force a text-only response
                )

                try:
                    client = self._require_client()
                    if streaming:
                        async for chunk in await client.aio.models.generate_content_stream(
                            model=self._model_name,
                            contents=contents,
                            config=final_config,
                        ):
                            if chunk.text:
                                yield StreamEvent(type="token", content=chunk.text)
                            if chunk.usage_metadata:
                                self.usage.record(
                                    prompt_tokens=chunk.usage_metadata.prompt_token_count or 0,
                                    completion_tokens=getattr(chunk.usage_metadata, "candidates_token_count", None) or 0,
                                    total_tokens=chunk.usage_metadata.total_token_count or 0,
                                )
                    else:
                        final_response = await client.aio.models.generate_content(
                            model=self._model_name,
                            contents=contents,
                            config=final_config,
                        )
                        extract_gemini_usage(final_response, self.usage, logger=logger)
                        if final_response.text:
                            yield StreamEvent(type="token", content=final_response.text)

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

                logger.info("Tool call: %s(%s)", fc_name, fc_args)
                yield StreamEvent(type="tool_start", tool=fc_name, arguments=fc_args)

                call_record = ToolCall(tool=fc_name, arguments=fc_args)

                try:
                    result = await tool_executor(fc_name, fc_args)
                    call_record.result = result
                    logger.info("Tool result: %s", str(result)[:200])
                    yield StreamEvent(type="tool_end", tool=fc_name, result=result)
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    result = {"error": error_msg}
                    call_record.error = error_msg
                    logger.warning("Tool error: %s", error_msg)
                    yield StreamEvent(type="tool_end", tool=fc_name, error=error_msg)

                tool_history.append(call_record)
                func_response_parts.append(
                    Part.from_function_response(name=fc_name, response=result)
                )

            contents.append(Content(role="tool", parts=func_response_parts))

        # --- Max iterations exhausted: fallback answer ---
        logger.warning("ReAct hit max iterations (%d). Requesting final answer.", max_iterations)
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
            if streaming:
                async for chunk in await client.aio.models.generate_content_stream(
                    model=self._model_name,
                    contents=contents,
                    config=fallback_config,
                ):
                    if chunk.text:
                        yield StreamEvent(type="token", content=chunk.text)
            else:
                fallback_response = await client.aio.models.generate_content(
                    model=self._model_name,
                    contents=contents,
                    config=fallback_config,
                )
                extract_gemini_usage(fallback_response, self.usage, logger=logger)
                if fallback_response.text:
                    yield StreamEvent(type="token", content=fallback_response.text)

            self.usage.log(logger, model=self._model_name, context="react_fallback")
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


    async def handle_model_error(
        self,
        db: AsyncSession,
        model: str,
        error: RateLimitError,
        api_key_manager: APIKeyManager,
    ) -> None:
        """Set a per-model cooldown and switch to another key+model if available.

        Strategy:
        - Mark only *model* on the current key as cooling down (not the whole key).
        - Call pick_available_key to find any ACTIVE key with no cooldown for this model.
        - If found, swap the client to that key.
        - If none found, raise LLMUnavailable so the caller can surface a clear error.
        """
        reason = "exhausted" if error.is_daily else "rate_limit"
        logger.warning(
            "Model cooldown: key=%s model=%s reason=%s",
            self._current_key_id, model, reason,
        )
        repo = APIKeyRepository(db)
        await repo.set_model_cooldown(self._current_key_id, model, reason)

        available_key = await repo.pick_available_key(self._provider, model)
        if available_key is None:
            raise LLMUnavailable(
                f"All active keys have a cooldown for model '{model}'. "
                "Try again later or add another API key."
            )

        raw_key = api_key_manager.fernet.decrypt(
            available_key.encrypted_key.encode()
        ).decode()
        self._current_key_id = available_key.id
        self._client = genai.Client(api_key=raw_key)
        logger.info("Switched to key=%s for model=%s", self._current_key_id, model)

    async def ensure_model_key(
        self,
        db: AsyncSession,
        model: str,
        api_key_manager: APIKeyManager,
    ) -> bool:
        """Check if the current key is on cooldown for this model. If so, swap it out."""
        repo = APIKeyRepository(db)
        if self._current_key_id:
            if await api_key_manager.is_model_available_for_key(self._current_key_id, model):
               return  False# Current key is completely fine

        # If we reach here, we need to swap!
        logger.info("Current key %s is not available for model %s. Searching for backup...", self._current_key_id, model)
        available_key = await repo.pick_available_key(self._provider, model)
        if available_key is None:
            raise LLMUnavailable(f"No active keys available for model '{model}'. All are on cooldown.")

        raw_key = api_key_manager.fernet.decrypt(
            available_key.encrypted_key.encode()
        ).decode()
        self._current_key_id = available_key.id
        self._client = genai.Client(api_key=raw_key)
        logger.info("Pre-flight: Switched to backup key=%s for model=%s", self._current_key_id, model)
        return True


    # ----- shared helper -----

    def _require_client(self) -> genai.Client:
        if self._client is None:
            raise LLMUnavailable("Gemini client is not initialized")
        return self._client

    async def _call(self, prompt: str, config: GenerateContentConfig) -> str:
        client = self._require_client()
        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        extract_gemini_usage(response, self.usage, logger=logger)
        self.usage.log(logger, model=self._model_name, context="generate")

        if response.text is None:
            raise RuntimeError("Gemini returned empty response")
        return response.text
