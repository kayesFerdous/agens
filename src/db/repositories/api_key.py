from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, load_only

from db.models import APIKey, KeyStatus
from config.logging import get_logger

logger = get_logger(__name__)

COOLDOWN_SECONDS = {
    "rate_limit": 60,      # 1 minute
    "exhausted":  86400,   # 24 hours
}


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


class APIKeyRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_key_usable_now(self, key_id: str, provider: str | None = None) -> bool:
        conditions = [
            APIKey.id == key_id,
            APIKey.status == KeyStatus.ACTIVE,
        ]

        if provider:
            conditions.append(APIKey.provider == provider)

        stmt = select(1).where(*conditions).limit(1)

        result = await self.session.scalar(stmt)
        return result is not None

    async def insert(self, api_key: APIKey) -> APIKey:
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key

    async def get_by_id(self, key_id: str) -> APIKey | None:
        result = await self.session.execute(
            select(APIKey)
            .where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        result = await self.session.execute(
            select(APIKey)
            .options(load_only(APIKey.id))
            .where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def list_keys(
        self,
        provider: str | None = None,
        status: KeyStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[APIKey]:
        stmt = (
            select(APIKey)
            .options(
                defer(APIKey.encrypted_key),
                defer(APIKey.key_hash),
            )
            .order_by(APIKey.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        if provider:
            stmt = stmt.where(APIKey.provider == provider)

        if status:
            stmt = stmt.where(APIKey.status == status)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, key_id: str, status: KeyStatus) -> None:
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(status=status)
        )
        await self.session.commit()

    async def record_usage(self, key_id: str) -> None:
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                last_used_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

    async def increment_failure(self, key_id: str) -> int:
        # Legacy compatibility: failure counters were removed from the schema.
        return 0

    async def reset_failures(self, key_id: str) -> None:
        # Legacy compatibility: failure counters were removed from the schema.
        return None

    async def check_cooldown(self, provider: str) -> None:
        # No global cooldown timestamp exists anymore; model-specific cooldowns are
        # tracked in `model_cooldowns`. Keep this method as a no-op for callers.
        return None

    async def get_active_by_provider(self, provider: str) -> list[APIKey]:
        await self.check_cooldown(provider=provider)
        result = await self.session.execute(
            select(APIKey)
            .options(load_only(
                APIKey.id,
                APIKey.encrypted_key,
                APIKey.last_used_at,
                APIKey.model_cooldowns,  # required by is_model_available()
            ))
            .where(
                APIKey.provider == provider,
                APIKey.status == KeyStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())

    async def set_cooldown(
        self, key_id: str, seconds: int, status: KeyStatus = KeyStatus.RATE_LIMITED
    ) -> None:
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(
                status=status,
            )
        )
        await self.session.commit()

    async def clear_cooldown(self, key_id: str) -> None:
        """Call this when a previously rate-limited key succeeds again."""
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(status=KeyStatus.ACTIVE)
        )
        await self.session.commit()

    async def delete_by_id(self, key_id: str) -> bool:
        result = await self.session.execute(delete(APIKey).where(APIKey.id == key_id))
        await self.session.commit()
        return (getattr(result, "rowcount", 0) or 0) > 0

    # --- Model Cooldowns ---

    async def set_model_cooldown(
        self,
        key_id: str,
        model: str,
        reason: str,  # "rate_limit" | "exhausted"
    ) -> APIKey | None:
        key = await self.get_by_id(key_id)
        if not key:
            return None

        delay = COOLDOWN_SECONDS.get(reason, 60)
        cooldowns: dict = dict(key.model_cooldowns or {})
        cooldowns[model] = {
            "until": (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(),
            "reason": reason,
        }
        key.model_cooldowns = cooldowns  # reassign so SQLAlchemy tracks the change
        await self.session.commit()
        return key

    async def clear_model_cooldown(
        self,
        key: APIKey,
        model: str,
    ) -> None:
        if key and key.model_cooldowns and model in key.model_cooldowns:
            cooldowns = dict(key.model_cooldowns)
            del cooldowns[model]
            key.model_cooldowns = cooldowns
            await self.session.commit()

    async def cleanup_expired_cooldowns(self, key: APIKey) -> None:
        """Removes all expired model cooldowns from a key on the go."""
        if not key.model_cooldowns:
            return
            
        now = datetime.now(timezone.utc)
        expired = [
            m for m, entry in key.model_cooldowns.items()
            if entry.get("until") and datetime.fromisoformat(entry["until"]) <= now
        ]
        
        if expired:
            cooldowns = dict(key.model_cooldowns)
            for m in expired:
                del cooldowns[m]
            key.model_cooldowns = cooldowns
            await self.session.commit()

    async def pick_available_key(self, provider: str, model: str) -> APIKey | None:
        """Returns the first ACTIVE key that has no cooldown for the given model.

        Also cleans up any expired cooldown entries so they don't accumulate.
        """
        keys = await self.get_active_by_provider(provider)
        for key in keys:
            await self.cleanup_expired_cooldowns(key)
            if is_model_available(key, model):
                return key
        return None
