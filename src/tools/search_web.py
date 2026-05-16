# tools/search_web.py — stateless web search with model-aware key resolution and one-shot retry
from __future__ import annotations

from typing import Any

from cryptography.fernet import Fernet
from openai import APIStatusError, APITimeoutError, AsyncOpenAI

from config.logging import get_logger
from core.tool_interface import Tool
from core.types import Usage
from db.database import async_session
from db.repositories.api_key import APIKeyRepository
from llm.errors import RateLimitError, normalize_error
from llm.providers import PROVIDER_DEFAULTS
from services.api_key_manager import APIKeyManager, SEARCH_MODELS

logger = get_logger(__name__)


class SearchUnavailableError(Exception):
    pass


_EXHAUSTED_MSG = (
    "Search is unavailable: no active API key supports any search-capable model "
    f"(tried: {', '.join(SEARCH_MODELS)})."
)


async def _do_search(raw_key: str, model: str, query: str, usage: Usage) -> dict:
    """Execute a single grounded-search call and return the result dict."""
    client = AsyncOpenAI(
        api_key=raw_key,
        base_url=PROVIDER_DEFAULTS["gemini"]["base_url"],
        timeout=60.0,
    )
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": query}],
        tools=[{"type": "google_search"}],  # type: ignore[list-item]
        temperature=1.0,
    )

    if response.usage:
        usage.record(
            prompt_tokens=response.usage.prompt_tokens or 0,
            completion_tokens=response.usage.completion_tokens or 0,
            total_tokens=response.usage.total_tokens or 0,
        )
        usage.log(logger, model=model, context="search_web")

    content = response.choices[0].message.content if response.choices else ""
    if not content:
        return {"answer": "", "queries": []}

    return {
        "answer": content[:1600],  # ~400 tokens; truncate to keep context lean
        "queries": [],
    }


class WebSearchTool(Tool):
    """Web search via Gemini's Google Search grounding.

    The tool is stateless with respect to API keys: it opens a short-lived DB
    session per search call to read current key availability, then closes it.
    This matches the same per-call session pattern used by the agent loop.

    Threading note: Tool.execute() runs inside asyncio.to_thread(), which means
    the asyncio event loop is already running on the calling thread.  We use
    asyncio.run_coroutine_threadsafe() to schedule coroutines onto that loop
    from within the worker thread instead of calling loop.run_until_complete()
    (which would deadlock).
    """

    def __init__(self, fernet: Fernet, usage: Usage | None = None) -> None:
        self._fernet = fernet
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

    async def _get_search_pair(self) -> tuple[str, str] | None:
        """Open a short-lived session, resolve the best (raw_key, model), close session."""
        async with async_session() as db:
            manager = APIKeyManager(repo=APIKeyRepository(db), fernet=self._fernet)
            pair = await manager.get_search_key_and_model()
            if pair is None:
                return None
            key, model = pair
            raw_key = self._fernet.decrypt(key.encrypted_key.encode()).decode()
            return raw_key, model

    async def execute(self, **kwargs: Any) -> dict:
        query: str = kwargs["query"]
        logger.info("Web search: %s", query)

        resolved = await self._get_search_pair()
        if resolved is None:
            raise SearchUnavailableError(_EXHAUSTED_MSG)

        raw_key, model = resolved

        try:
            result = await _do_search(raw_key, model, query, self.usage)
            logger.info("Search succeeded (model=%s)", model)
            return result

        except APIStatusError as first_err:
            normalized = normalize_error(first_err, provider="gemini")
            if not isinstance(normalized, RateLimitError):
                raise SearchUnavailableError(str(normalized)) from first_err
            logger.warning(
                "Search failed on first attempt (model=%s): %s — retrying",
                model, normalized,
            )
        except (APITimeoutError, RateLimitError) as first_err:
            logger.warning(
                "Search failed on first attempt (model=%s): %s — retrying",
                model, first_err,
            )

        # --- One retry: ask the manager for the next available (key, model) pair ---
        retry = await self._get_search_pair()
        if retry is None:
            raise SearchUnavailableError(_EXHAUSTED_MSG)

        retry_raw, retry_model = retry

        try:
            result = await _do_search(retry_raw, retry_model, query, self.usage)
            logger.info("Search retry succeeded (model=%s)", retry_model)
            return result

        except APIStatusError as retry_err:
            normalized = normalize_error(retry_err, provider="gemini")
            logger.error("Search retry also failed (model=%s): %s", retry_model, normalized)
            raise SearchUnavailableError(_EXHAUSTED_MSG) from retry_err
        except (APITimeoutError, RateLimitError) as retry_err:
            logger.error("Search retry also failed (model=%s): %s", retry_model, retry_err)
            raise SearchUnavailableError(_EXHAUSTED_MSG) from retry_err
