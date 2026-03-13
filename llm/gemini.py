# llm/gemini.py
from __future__ import annotations
import os
from google import genai
from google.genai import types
from llm.base import LLM


class GeminiLLM(LLM):
    def __init__(self, model: str = "gemini-2.5-flash-lite", api_key: str | None = None) -> None:
        key = api_key or os.environ["GOOGLE_API_KEY"]
        self._client = genai.Client(api_key=key)
        self._model = model

    def generate(self, prompt: str, system: str = "") -> str:
        config = types.GenerateContentConfig(
            system_instruction=system or None,
            response_mime_type="application/json",
            temperature=0,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        if response.text is None:
            raise RuntimeError("Gemini returned empty response")
        return response.text
