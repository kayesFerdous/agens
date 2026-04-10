# llm/api_key_manager.py
"""
Production-grade API key rotation manager.

Handles multiple API keys with automatic failover when rate limits are hit.
Similar to how Codex, Copilot CLI, and Gemini CLI handle key rotation.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar, ParamSpec
from functools import wraps

from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from google.genai.errors import ClientError

from config.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class KeyStatus(Enum):
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"  # Daily quota exhausted
    INVALID = "invalid"


@dataclass
class APIKeyState:
    """Tracks the health state of a single API key."""

    key: str
    status: KeyStatus = KeyStatus.HEALTHY
    last_used: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0
    # Masked key for logging (show only last 4 chars)
    masked: str = field(init=False)

    def __post_init__(self) -> None:
        self.masked = f"...{self.key[-4:]}" if len(self.key) > 4 else "****"

    def is_available(self) -> bool:
        """Check if this key can be used right now."""
        if self.status == KeyStatus.INVALID:
            return False
        if self.status in (KeyStatus.RATE_LIMITED, KeyStatus.EXHAUSTED):
            # Check if cooldown has passed
            if time.time() >= self.cooldown_until:
                self.status = KeyStatus.HEALTHY
                self.failure_count = 0
                logger.info("Key %s cooldown expired, marking healthy", self.masked)
                return True
            return False
        return True

    def mark_rate_limited(self, cooldown_seconds: float = 60.0) -> None:
        """Mark this key as rate limited with a cooldown period."""
        self.status = KeyStatus.RATE_LIMITED
        self.failure_count += 1
        self.cooldown_until = time.time() + cooldown_seconds
        logger.warning(
            "Key %s rate limited (failures: %d), cooldown until %.0fs",
            self.masked,
            self.failure_count,
            cooldown_seconds,
        )

    def mark_exhausted(self, cooldown_seconds: float = 86400.0) -> None:
        """Mark this key as quota exhausted (daily quota - 24hr cooldown)."""
        self.status = KeyStatus.EXHAUSTED
        self.cooldown_until = time.time() + cooldown_seconds
        logger.warning(
            "Key %s quota exhausted, cooldown for %.1f hours",
            self.masked,
            cooldown_seconds / 3600,
        )

    def mark_invalid(self) -> None:
        """Mark this key as permanently invalid."""
        self.status = KeyStatus.INVALID
        logger.error("Key %s marked as invalid (bad credentials)", self.masked)

    def mark_success(self) -> None:
        """Mark a successful use of this key."""
        self.last_used = time.time()
        if self.status != KeyStatus.HEALTHY:
            self.status = KeyStatus.HEALTHY
            self.failure_count = 0


class APIKeyManager:
    """
    Manages multiple API keys with automatic rotation and failover.

    Usage:
        manager = APIKeyManager(["key1", "key2", "key3"])
        key = manager.get_available_key()  # Returns best available key
        manager.report_success(key)        # On success
        manager.report_rate_limit(key)     # On rate limit error
    """

    def __init__(
        self,
        api_keys: list[str],
        *,
        rate_limit_cooldown: float = 60.0,
        quota_exhausted_cooldown: float = 3600.0,
    ) -> None:
        if not api_keys:
            raise ValueError("At least one API key is required")

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_keys: list[str] = []
        for k in api_keys:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                unique_keys.append(k)

        self._keys = [APIKeyState(key=k) for k in unique_keys]
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._rate_limit_cooldown = rate_limit_cooldown
        self._quota_exhausted_cooldown = quota_exhausted_cooldown

        logger.info(
            "APIKeyManager initialized with %d key(s): %s",
            len(self._keys),
            ", ".join(k.masked for k in self._keys),
        )

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def available_keys(self) -> int:
        return sum(1 for k in self._keys if k.is_available())

    def get_available_key(self) -> str:
        """
        Get the next available API key using round-robin with failover.

        Raises:
            RuntimeError: If no keys are available (all rate limited/exhausted).
        """
        # Try all keys starting from current index
        for _ in range(len(self._keys)):
            key_state = self._keys[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._keys)

            if key_state.is_available():
                logger.debug("Using key %s", key_state.masked)
                return key_state.key

        # No keys available - find the one with shortest cooldown
        soonest = min(self._keys, key=lambda k: k.cooldown_until)
        wait_time = max(0, soonest.cooldown_until - time.time())

        raise AllKeysExhaustedError(
            f"All {len(self._keys)} API keys are rate limited or exhausted. "
            f"Next key available in {wait_time:.0f}s",
            retry_after=wait_time,
        )

    async def get_available_key_async(self) -> str:
        """Thread-safe version of get_available_key."""
        async with self._lock:
            return self.get_available_key()

    def _find_key_state(self, key: str) -> APIKeyState | None:
        """Find the state object for a given key."""
        for k in self._keys:
            if k.key == key:
                return k
        return None

    def report_success(self, key: str) -> None:
        """Report successful use of a key."""
        if state := self._find_key_state(key):
            state.mark_success()

    def report_rate_limit(self, key: str) -> None:
        """Report that a key hit a rate limit (short cooldown)."""
        if state := self._find_key_state(key):
            # Exponential backoff based on failure count
            cooldown = self._rate_limit_cooldown * (2 ** min(state.failure_count, 4))
            state.mark_rate_limited(cooldown)

    def report_quota_exhausted(self, key: str) -> None:
        """Report that a key's daily quota is exhausted (long cooldown)."""
        if state := self._find_key_state(key):
            state.mark_exhausted(self._quota_exhausted_cooldown)

    def report_invalid(self, key: str) -> None:
        """Report that a key is invalid (permanent)."""
        if state := self._find_key_state(key):
            state.mark_invalid()

    def get_status(self) -> dict:
        """Get current status of all keys for debugging."""
        return {
            "total_keys": self.total_keys,
            "available_keys": self.available_keys,
            "keys": [
                {
                    "masked": k.masked,
                    "status": k.status.value,
                    "failure_count": k.failure_count,
                    "cooldown_remaining": max(0, k.cooldown_until - time.time()),
                }
                for k in self._keys
            ],
        }


class AllKeysExhaustedError(Exception):
    """Raised when all API keys are rate limited or exhausted."""

    def __init__(self, message: str, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def with_key_rotation(
    manager: APIKeyManager,
    max_retries: int = 3,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that adds automatic key rotation to async functions.

    The decorated function must accept `api_key` as a keyword argument.

    Usage:
        @with_key_rotation(key_manager)
        async def call_gemini(prompt: str, *, api_key: str) -> str:
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error: Exception | None = None

            for attempt in range(max_retries):
                try:
                    key = await manager.get_available_key_async()
                    kwargs["api_key"] = key
                    result = await func(*args, **kwargs)
                    manager.report_success(key)
                    return result

                except (ResourceExhausted, TooManyRequests) as e:
                    # Rate limit hit - rotate to next key
                    last_error = e
                    error_msg = str(e).lower()

                    if "quota" in error_msg or "daily" in error_msg:
                        manager.report_quota_exhausted(key)
                    else:
                        manager.report_rate_limit(key)

                    logger.warning(
                        "Attempt %d/%d failed with rate limit, rotating key",
                        attempt + 1,
                        max_retries,
                    )

                except ClientError as e:
                    last_error = e
                    error_msg = str(e).lower()

                    if "api_key" in error_msg or "invalid" in error_msg or "401" in error_msg:
                        manager.report_invalid(key)
                    elif "429" in error_msg or "rate" in error_msg:
                        manager.report_rate_limit(key)
                    else:
                        # Unknown error - don't retry with different key
                        raise

                    logger.warning(
                        "Attempt %d/%d failed with client error: %s",
                        attempt + 1,
                        max_retries,
                        e,
                    )

            # All retries exhausted
            raise last_error or RuntimeError("All retry attempts failed")

        return wrapper  # type: ignore

    return decorator
