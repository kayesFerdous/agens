# llm/openai.py
from __future__ import annotations
from llm.base import LLM


class OpenAILLM(LLM):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        raise NotImplementedError("OpenAI provider not yet implemented")

    def generate(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError
