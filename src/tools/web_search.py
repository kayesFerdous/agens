from __future__ import annotations

import asyncio
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException

from core.tool_interface import Tool

_MAX_RETRIES = 3
_RETRY_DELAY = 2.0  # seconds; multiplied by attempt number on rate-limit


def _search_sync(
    query: str,
    *,
    region: str,
    timelimit: str | None,
    max_results: int,
) -> list[dict]:
    """
    Blocking DuckDuckGo text search.
    Runs inside asyncio.to_thread so it never blocks the event loop.
    """
    with DDGS() as ddgs:
        return list(
            ddgs.text(
                query,
                region=region,
                timelimit=timelimit,
                max_results=max_results,
            )
        )


class WebSearchTool(Tool):
    """Search the web via DuckDuckGo — no API key, no cost."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information, recent news, facts, or any topic. "
            "Returns ranked results with titles, URLs, and plain-text snippets. "
            "Use this whenever you need up-to-date information or are uncertain about a fact. "
            "After getting results, use web_fetch on a specific URL to read its full content."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (1–10). Defaults to 6.",
                },
                "time_filter": {
                    "type": "string",
                    "description": (
                        "Restrict results by recency. "
                        "'d' = past day, 'w' = past week, "
                        "'m' = past month, 'y' = past year. "
                        "Omit for all-time results."
                    ),
                    "enum": ["d", "w", "m", "y"],
                },
                "region": {
                    "type": "string",
                    "description": (
                        "Region/language code for results, e.g. 'us-en', 'gb-en', "
                        "'wt-wt' (worldwide). Defaults to 'wt-wt'."
                    ),
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> dict:
        query: str = kwargs["query"].strip()
        if not query:
            return {"status": "error", "message": "Query must not be empty."}

        max_results: int = max(1, min(int(kwargs.get("max_results", 6)), 10))
        time_filter: str | None = kwargs.get("time_filter")
        region: str = kwargs.get("region", "wt-wt")

        last_error: str = ""

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                raw = await asyncio.to_thread(
                    _search_sync,
                    query,
                    region=region,
                    timelimit=time_filter,
                    max_results=max_results,
                )

                if not raw:
                    return {
                        "status": "no_results",
                        "query": query,
                        "results": [],
                        "message": "No results found for this query.",
                    }

                results = [
                    {
                        "title": item.get("title", "").strip(),
                        "url": item.get("href", "").strip(),
                        "snippet": item.get("body", "").strip(),
                    }
                    for item in raw
                    if item.get("href")
                ]

                return {
                    "status": "success",
                    "query": query,
                    "result_count": len(results),
                    "results": results,
                }

            except RatelimitException:
                last_error = "DuckDuckGo rate limit reached."
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAY * attempt)

            except DDGSException as exc:
                last_error = str(exc)[:200]
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAY)

            except Exception as exc:
                last_error = str(exc)[:200]
                break  # non-retryable

        return {
            "status": "error",
            "query": query,
            "message": last_error or "Unknown error during web search.",
        }
