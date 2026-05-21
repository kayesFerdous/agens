# llm/errors.py
from __future__ import annotations
from openai import APIStatusError


class LLMError(Exception):
    """Base for all LLM errors surfaced to agent.py."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        is_transient: bool = False,
        is_auth_error: bool = False,
    ) -> None:
        self.status_code = status_code
        self.is_transient = is_transient
        self.is_auth_error = is_auth_error
        super().__init__(message)


class RateLimitError(LLMError):
    def __init__(self, *, key_id: str, retry_after: int, is_daily: bool = False):
        self.key_id = key_id
        self.retry_after = retry_after
        self.is_daily = is_daily
        super().__init__(
            f"Rate limited (key={key_id}, retry_after={retry_after}s, daily={is_daily})",
            status_code=429,
            is_transient=True,
        )


class LLMUnavailableError(LLMError):
    """Thrown when no keys are available or the provider is unreachable."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        is_transient: bool = False,
    ) -> None:
        super().__init__(message, status_code=status_code, is_transient=is_transient)


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

    if e.status_code in (401, 403):
        return LLMError(
            f"{provider} authentication failed (HTTP {e.status_code}): {e.message}",
            status_code=e.status_code,
            is_auth_error=True,
        )

    if e.status_code >= 500:
        return LLMError(
            f"{provider} server error (HTTP {e.status_code}): {e.message}",
            status_code=e.status_code,
            is_transient=True,
        )

    # Re-wrap everything else — at minimum gives you a typed exception.
    return LLMError(
        f"{provider} API error {e.status_code}: {e.message}",
        status_code=e.status_code,
    )


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
