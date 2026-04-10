# llm/gemini.py
from __future__ import annotations
import os
from collections.abc import Callable, AsyncIterator, Awaitable
from typing import Any
from google import genai
from google.genai.types import Content, FunctionDeclaration, GenerateContentConfig, Part, Tool
from google.api_core.exceptions import ResourceExhausted, TooManyRequests

from llm.base import LLM, ReactResult
from llm.gemini_usage import extract_gemini_usage
from llm.depricated_api_key_manager import APIKeyManager, AllKeysExhaustedError
from core.types import StreamEvent, ToolCall, Usage
from config.logging import get_logger

logger = get_logger(__name__)


class GeminiLLM(LLM):
    """Google Gemini backend implementing all generation modes with key rotation."""

    def __init__(
        self,
        usage: Usage,
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
        # key_manager: APIKeyManager | None = None,
    ) -> None:
        self.usage = usage
        self._model = model
        # self._key_manager = key_manager

        # If key_manager is provided, use it; otherwise use single key (backwards compat)
        if key_manager:
            initial_key = key_manager.get_available_key()
            self._client = genai.Client(api_key=initial_key)
            self._current_key = initial_key
        else:
            single_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
            self._client = genai.Client(api_key=single_key)
            self._current_key = single_key

    def _rotate_client_if_needed(self) -> None:
        """Rotate to a new API key if manager is available."""
        if self._key_manager:
            new_key = self._key_manager.get_available_key()
            if new_key != self._current_key:
                self._client = genai.Client(api_key=new_key)
                self._current_key = new_key
                logger.info("Rotated to new API key: ...%s", new_key[-4:])

    async def _with_retry(self, operation: Callable[[], Awaitable[Any]], max_retries: int = 3) -> Any:
        """Execute operation with automatic key rotation on rate limit errors."""
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                result = await operation()
                if self._key_manager:
                    self._key_manager.report_success(self._current_key)
                return result

            except (ResourceExhausted, TooManyRequests) as e:
                last_error = e
                error_msg = str(e).lower()

                if self._key_manager:
                    if "quota" in error_msg or "daily" in error_msg:
                        self._key_manager.report_quota_exhausted(self._current_key)
                    else:
                        self._key_manager.report_rate_limit(self._current_key)

                    logger.warning(
                        "Rate limit hit (attempt %d/%d), rotating key...",
                        attempt + 1,
                        max_retries,
                    )

                    try:
                        self._rotate_client_if_needed()
                    except AllKeysExhaustedError:
                        raise
                else:
                    # No key manager - can't rotate
                    raise

            except Exception as e:
                # For non-rate-limit errors, don't retry
                raise

        raise last_error or RuntimeError("All retry attempts failed")

    # ----- plain text completion -----

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> str:
        config = GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        return await self._call(prompt, config)

    # ----- structured / JSON completion -----

    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        config = GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        )
        return await self._call(prompt, config)

    # ----- streaming completion -----

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> AsyncIterator[str]:
        config = GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    # ----- ReAct loop with function calling -----

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
    ) -> ReactResult:
        message_history = message_history or []
        # Build function declarations from tool schemas
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
            logger.info("ReAct iteration %d", iteration + 1)

            # Reduce old tool outputs to save tokens
            self._reduce_tool_outputs(contents, truncated_indices)

            async def _do_react_call():
                return await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )

            response = await self._with_retry(_do_react_call)

            extract_gemini_usage(response, self.usage, logger=logger)

            if not response.candidates:
                raise RuntimeError("Gemini returned no candidates.")

            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                reason = getattr(candidate, "finish_reason", "UNKNOWN")
                raise RuntimeError(f"Candidate returned no content or parts. Finish reason: {reason}")

            content_parts = candidate.content.parts

            # Collect all function calls from the response
            function_calls = [
                part for part in content_parts
                if part.function_call
            ]

            # If no function calls, the model returned a text answer — we're done
            if not function_calls:
                answer = content_parts[0].text or ""
                self.usage.log(logger, model=self._model, context="react")
                logger.info("ReAct complete after %d iteration(s)", iteration + 1)
                return ReactResult(answer=answer, tool_calls=tool_history, usage=self.usage)

            # Append the model's response (with function calls) to history
            contents.append(candidate.content)

            # Execute each function call and build responses
            func_response_parts: list[Part] = []
            for part in function_calls:
                fc = part.function_call
                # Help the type checker understand fc and fc.name are not None
                if not fc or not fc.name:
                    continue

                fc_name = fc.name
                fc_args = dict(fc.args) if fc.args else {}

                logger.info("Tool call: %s(%s)", fc_name, fc_args)

                call_record = ToolCall(tool=fc_name, arguments=fc_args)

                try:
                    result = await tool_executor(fc_name, fc_args)
                    call_record.result = result
                    logger.info("Tool result: %s", str(result)[:200])
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    result = {"error": error_msg}
                    call_record.error = error_msg
                    logger.warning("Tool error: %s", error_msg)

                tool_history.append(call_record)

                func_response_parts.append(
                    Part.from_function_response(
                        name=fc_name,
                        response=result,
                    )
                )

            # Append all function responses to history
            contents.append(Content(role="tool", parts=func_response_parts))

        # Exhausted iterations — ask the model for a final answer without tools
        logger.warning("ReAct hit max iterations (%d). Requesting final answer.", max_iterations)
        contents.append(
            Content(
                role="user",
                parts=[Part.from_text(
                    text="You have used all available iterations. Provide your best answer now based on the information gathered so far."
                )],
            )
        )
        final_config = GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )

        async def _do_final_call():
            return await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=final_config,
            )

        final_response = await self._with_retry(_do_final_call)

        extract_gemini_usage(final_response, self.usage, logger=logger)
        self.usage.log(logger, model=self._model, context="react_fallback")

        answer = final_response.text or "(No answer produced)"
        return ReactResult(answer=answer, tool_calls=tool_history, usage=self.usage)

    # ----- Streaming ReAct loop -----

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
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )

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
                async for chunk in await self._client.aio.models.generate_content_stream(
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
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=fallback_config,
        ):
            if chunk.text:
                yield StreamEvent(type="token", content=chunk.text)

        self.usage.log(logger, model=self._model, context="react_stream_fallback")
        yield StreamEvent(type="done", usage=self.usage, tool_calls=tool_history)

    def _reduce_tool_outputs(self, contents: list[Content], truncated_indices: set[int], max_chars: int = 500) -> None:
        """Truncate old tool outputs to reduce token usage, keeping the last output intact."""
        for i, content in enumerate(contents[:-1]):
            if i in truncated_indices or content.role != "tool" or not content.parts:
                continue

            new_parts = []
            for part in content.parts:
                if part.function_response and part.function_response.response:
                    response = part.function_response.response
                    truncated_response = {
                        key: value[:max_chars] + "... [truncated]"
                        if isinstance(value, str) and len(value) > max_chars
                        else value
                        for key, value in response.items()
                    }
                    new_parts.append(
                        Part.from_function_response(
                            name=part.function_response.name,
                            response=truncated_response,
                        )
                    )
                else:
                    new_parts.append(part)

            contents[i] = Content(role="tool", parts=new_parts)
            truncated_indices.add(i)


    # ----- shared helper -----

    async def _call(self, prompt: str, config: GenerateContentConfig) -> str:
        async def _do_call() -> str:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )

            extract_gemini_usage(response, self.usage, logger=logger)
            self.usage.log(logger, model=self._model, context="generate")

            if response.text is None:
                raise RuntimeError("Gemini returned empty response")
            return response.text

        return await self._with_retry(_do_call)
