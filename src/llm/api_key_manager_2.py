from dataclasses import dataclass
from enum import Enum


class KeyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
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


class APIKeyManager:
    def __init__(self) -> None:
        pass
