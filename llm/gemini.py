# llm/gemini.py
from __future__ import annotations
import os
from collections.abc import Iterator
from typing import Any
from google import genai
from google.genai import types
from llm.base import LLM


class GeminiLLM(LLM):
    """Google Gemini backend implementing all three generation modes."""

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

    # ----- shared helper -----

    def _call(self, prompt: str, config: types.GenerateContentConfig) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        if response.text is None:
            raise RuntimeError("Gemini returned empty response")
        return response.text