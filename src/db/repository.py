from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import APIKey, KeyStatus, Message, Session

# ─────────────────────────────────────────
# Session
# ─────────────────────────────────────────

async def insert_session(db: AsyncSession, title: str | None = None) -> Session:
    session = Session(title=title)
    db.add(session)
    await db.commit()
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.messages))
    )
    return result.scalars().one_or_none()


async def fetch_all_sessions(db: AsyncSession, limit: int = 20) -> list[Session]:
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


# ─────────────────────────────────────────
# Message
# ─────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list[dict] | None = None,
) -> Message:
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(message)
    await db.commit()
    return message


async def get_messages(
    db: AsyncSession, session_id: str, max_history: int = 3
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(max_history * 2)
    )
    return list(reversed(result.scalars().all()))


# ─────────────────────────────────────────
# API Key — CRUD
# ─────────────────────────────────────────

async def insert_api_key(db: AsyncSession, **kwargs) -> APIKey:
    key = APIKey(**kwargs)
    db.add(key)
    await db.commit()
    return key


async def get_api_key(db: AsyncSession, key_id: str) -> APIKey | None:
    return await db.get(APIKey, key_id)


async def get_active_keys(
    db: AsyncSession, provider: str | None = None
) -> list[APIKey]:
    """All ACTIVE keys, optionally filtered by provider."""
    q = select(APIKey).where(APIKey.status == KeyStatus.ACTIVE)
    if provider:
        q = q.where(APIKey.provider == provider)
    result = await db.execute(q)
    return list(result.scalars().all())


async def delete_api_key(db: AsyncSession, key_id: str) -> bool:
    key = await db.get(APIKey, key_id)
    if not key:
        return False
    await db.delete(key)
    await db.commit()
    return True


# ─────────────────────────────────────────
# API Key — Model Cooldowns
# ─────────────────────────────────────────

RETRY_DELAYS = {
    #              1st     2nd      3rd+
    "rate_limit":  [60,    300,     900],       # 1m → 5m → 15m
    "exhausted":   [3600,  21600,   86400],     # 1h → 6h → 24h
}


def _cooldown_seconds(reason: str, consecutive_failures: int) -> int:
    delays = RETRY_DELAYS.get(reason, [60])
    index = min(consecutive_failures - 1, len(delays) - 1)
    return delays[index]


async def set_model_cooldown(
    db: AsyncSession,
    key_id: str,
    model: str,
    reason: str,                    # "rate_limit" | "exhausted"
) -> APIKey | None:
    key = await db.get(APIKey, key_id)
    if not key:
        return None

    cooldowns: dict = dict(key.model_cooldowns or {})
    prev = cooldowns.get(model) or {}
    failures = prev.get("failures", 0) + 1
    delay = _cooldown_seconds(reason, failures)

    cooldowns[model] = {
        "until": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
        "reason": reason,
    }
    key.model_cooldowns = cooldowns     # reassign so SQLAlchemy tracks the change
    await db.commit()
    return key


async def clear_model_cooldown(
    db: AsyncSession, key_id: str, model: str
) -> APIKey | None:
    """Call this on a successful response to reset the model's failure state."""
    key = await db.get(APIKey, key_id)
    if not key or not key.model_cooldowns:
        return key

    cooldowns = dict(key.model_cooldowns)
    cooldowns.pop(model, None)          # remove entirely — absence means available
    key.model_cooldowns = cooldowns
    await db.commit()
    return key


def is_model_available(key: APIKey, model: str) -> bool:
    """Pure helper — no DB call needed."""
    if not key.model_cooldowns:
        return True
    entry = key.model_cooldowns.get(model)
    if not entry or entry.get("until") is None:
        return True
    return datetime.fromisoformat(entry["until"]) <= datetime.now(timezone.utc)


def get_model_cooldown_info(key: APIKey, model: str) -> dict | None:
    """Returns cooldown entry if the model is currently blocked, else None."""
    if not key.model_cooldowns:
        return None
    entry = key.model_cooldowns.get(model)
    if not entry or entry.get("until") is None:
        return None
    until = datetime.fromisoformat(entry["until"])
    if until <= datetime.now(timezone.utc):
        return None
    return {
        "model": model,
        "available_at": until,
        "reason": entry.get("reason"),
        "wait_seconds": int((until - datetime.now(timezone.utc)).total_seconds()),
    }


async def pick_available_key(
    db: AsyncSession, provider: str, model: str
) -> APIKey | None:
    """Returns the first ACTIVE key that has no cooldown for the given model."""
    keys = await get_active_keys(db, provider=provider)
    for key in keys:
        if is_model_available(key, model):
            return key
    return None
