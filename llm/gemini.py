# llm/gemini.py
from __future__ import annotations
import os
from collections.abc import Callable, Iterator
from typing import Any
from google import genai
from google.genai import types
from llm.base import LLM, ReactResult
from core.types import ToolCall, Usage
from config.logging import get_logger

logger = get_logger(__name__)


def _extract_usage(response: types.GenerateContentResponse, usage: Usage) -> None:
    """Safely extract token counts from a Gemini response into *usage*.

    Logs a warning instead of crashing when metadata is missing or partial.
    """
    meta = response.usage_metadata
    if meta is None:
        logger.warning("Gemini response missing usage_metadata")
        return

    usage.record(
        prompt_tokens=meta.prompt_token_count or 0,
        completion_tokens=getattr(meta, "candidates_token_count", None) or 0,
        total_tokens=meta.total_token_count or 0,
    )


class GeminiLLM(LLM):
    """Google Gemini backend implementing all generation modes."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
    ) -> None:
        self._client = genai.Client(api_key=api_key or os.environ["GOOGLE_API_KEY"])
        self._model = model

    # ----- plain text completion -----

    def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        return self._call(prompt, config)

    # ----- structured / JSON completion -----

    def generate_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        )
        return self._call(prompt, config)

    # ----- streaming completion -----

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> Iterator[str]:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
        )
        for chunk in self._client.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    # ----- ReAct loop with function calling -----

    def react(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_iterations: int = 10,
        temperature: float = 0,
    ) -> ReactResult:
        # Build function declarations from tool schemas
        func_decls = [
            types.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in tool_schemas
        ]
        tools = [types.Tool(function_declarations=func_decls)]

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=tools,
            temperature=temperature,
        )

        # Conversation history starts with the user request
        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_request)])
        ]

        tool_history: list[ToolCall] = []
        usage: Usage = Usage()

        for iteration in range(max_iterations):
            logger.info("ReAct iteration %d", iteration + 1)

            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )

            _extract_usage(response, usage)

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
                usage.log(logger, model=self._model, context="react")
                logger.info("ReAct complete after %d iteration(s)", iteration + 1)
                return ReactResult(answer=answer, tool_calls=tool_history, usage=usage)

            # Append the model's response (with function calls) to history
            contents.append(candidate.content)

            # Execute each function call and build responses
            func_response_parts: list[types.Part] = []
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
                    result = tool_executor(fc_name, fc_args)
                    call_record.result = result
                    logger.info("Tool result: %s", str(result)[:200])
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    result = {"error": error_msg}
                    call_record.error = error_msg
                    logger.warning("Tool error: %s", error_msg)

                tool_history.append(call_record)

                func_response_parts.append(
                    types.Part.from_function_response(
                        name=fc_name,
                        response=result,
                    )
                )

            # Append all function responses to history
            contents.append(types.Content(role="tool", parts=func_response_parts))

        # Exhausted iterations — ask the model for a final answer without tools
        logger.warning("ReAct hit max iterations (%d). Requesting final answer.", max_iterations)
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text="You have used all available iterations. Provide your best answer now based on the information gathered so far."
                )],
            )
        )
        final_config = types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=0.6,
        )
        final_response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=final_config,
        )

        _extract_usage(final_response, usage)
        usage.log(logger, model=self._model, context="react_fallback")

        answer = final_response.text or "(No answer produced)"
        return ReactResult(answer=answer, tool_calls=tool_history, usage=usage)

    # ----- shared helper -----

    def _call(self, prompt: str, config: types.GenerateContentConfig) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )

        usage = Usage()
        _extract_usage(response, usage)
        usage.log(logger, model=self._model, context="generate")

        if response.text is None:
            raise RuntimeError("Gemini returned empty response")
        return response.text
