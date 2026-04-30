# tools/search_web.py
from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from config.logging import get_logger
from core.tool_interface import Tool
from core.types import Usage
from llm.gemini_usage import extract_gemini_usage

logger = get_logger(__name__)

_SEARCH_CONFIG = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
    temperature=1.0,  # recommended by Google for grounded responses
)


class WebSearchTool(Tool):
    """Web search via Gemini's Google Search grounding.

    Uses a dedicated genai.Client so its grounded-search config stays
    fully isolated from the agent's main LLM (which uses function calling).
    """

    def __init__(
        self,
        client: genai.Client,
        *,
        model: str = "gemini-2.5-flash-lite",
        usage: Usage | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self.usage = usage or Usage()

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Web search for information beyond training data or requiring live/current data."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> dict:
        MAX_TOKEN = 400
        query: str = kwargs["query"]
        logger.info("Web search: %s", query)

        response = self._client.models.generate_content(
            model=self._model,
            contents=query,
            config=_SEARCH_CONFIG,
        )
        extract_gemini_usage(response, self.usage, logger=logger)

        if not response.text:
            return {"answer": "", "queries": [], "sources": []}

        # sources: list[dict[str, str]] = []
        queries_used: list[str] = []

        # if response.candidates and response.candidates[0].grounding_metadata:
        #     meta = response.candidates[0].grounding_metadata
        #     queries_used = list(meta.web_search_queries or [])
            # for chunk in meta.grounding_chunks or []:
                # if chunk.web:
                    # sources.append({
                    #     "title": chunk.web.title or "",
                    #     "url": chunk.web.uri or "",
                    # })

        logger.info(
            # "Search returned %d source(s) from %d query(ies)",
            "Search returned from %d query(ies)",
            # len(sources),
            len(queries_used),
        )

        return {
            "answer": response.text[:MAX_TOKEN*4], #NOTE: truncating output
            "queries": queries_used,
            # "sources": sources,
        }
