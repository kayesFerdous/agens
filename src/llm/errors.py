# llm/errors.py
from __future__ import annotations
from openai import APIStatusError


class LLMError(Exception):
    """Base for all LLM errors surfaced to agent.py."""


class RateLimitError(LLMError):
    def __init__(self, *, key_id: str, retry_after: int, is_daily: bool = False):
        self.key_id = key_id
        self.retry_after = retry_after
        self.is_daily = is_daily
        super().__init__(f"Rate limited (key={key_id}, retry_after={retry_after}s, daily={is_daily})")


class LLMUnavailableError(LLMError):
    """Thrown when no keys are available or the provider is unreachable."""


_DAILY_KEYWORDS = ("per day", "daily limit", "quota exceeded", "resource_exhausted")
_DAY_SECONDS = 86_400


def normalize_error(e: APIStatusError, *, provider: str) -> LLMError:
    """
    Turn an OpenAI SDK APIStatusError into one of our typed errors.
    Called in LLMClient whenever the SDK raises.
    """
    if e.status_code == 429:
        retry_after = _parse_retry_after(e)
        error_text = str(e).lower()
        is_daily = any(kw in error_text for kw in _DAILY_KEYWORDS)
        if retry_after is None:
            retry_after = _DAY_SECONDS if is_daily else 60
        # key_id isn't available in the error; caller must inject it.
        return RateLimitError(key_id="unknown", retry_after=retry_after, is_daily=is_daily)

    if e.status_code in (503, 529):
        return LLMUnavailableError(f"{provider} is temporarily unavailable (HTTP {e.status_code})")

    # Re-wrap everything else — at minimum gives you a typed exception.
    return LLMError(f"{provider} API error {e.status_code}: {e.message}")


def _parse_retry_after(e: APIStatusError) -> int | None:
    """Try to extract Retry-After from headers or response body."""
    # Standard HTTP header
    if hasattr(e, "response") and e.response is not None:
        raw = e.response.headers.get("retry-after") or e.response.headers.get("Retry-After")
        if raw:
            try:
                return int(raw)
            except ValueError:
                pass

    # Some providers embed retry delay in the JSON body
    try:
        import re, json
        body = e.response.text if hasattr(e, "response") and e.response else ""
        data = json.loads(body)
        # OpenAI / Groq style: {"error": {"message": "...", "code": "rate_limit_exceeded"}}
        # Some providers: {"error": {"details": [{"retryDelay": "30s"}]}}
        for detail in data.get("error", {}).get("details", []):
            raw_delay = detail.get("retryDelay", "")
            match = re.match(r"(\d+)", str(raw_delay))
            if match:
                return int(match.group(1))
    except Exception:
        pass

    return None
