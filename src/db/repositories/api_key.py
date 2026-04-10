from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import or_

from db.models import APIKey, KeyStatus


class APIKeyRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert(self, api_key: APIKey) -> APIKey:
        self.session.add(api_key)
        await self.session.commit()
        await self.session.refresh(api_key)
        return api_key

    async def get_by_id(self, key_id: str) -> APIKey | None:
        result = await self.session.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        result = await self.session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

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
                total_calls=APIKey.total_calls + 1,
            )
        )
        await self.session.commit()

    async def increment_failure(self, key_id: str) -> int:
        key = await self.get_by_id(key_id)
        key.consecutive_failures += 1 #type: ignore
        await self.session.commit()
        return key.consecutive_failures #type: ignore

    async def reset_failures(self, key_id: str) -> None:
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(consecutive_failures=0)
        )
        await self.session.commit()

    async def get_active_by_provider(self, provider: str) -> list[APIKey]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(APIKey).where(
                APIKey.provider == provider,
                APIKey.status == KeyStatus.ACTIVE,
                or_(
                    APIKey.cooldown_until.is_(None),
                    APIKey.cooldown_until <= now,        # cooldown expired → eligible again
                )
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
                cooldown_until=datetime.now(timezone.utc) + timedelta(seconds=seconds),
            )
        )
        await self.session.commit()

    async def clear_cooldown(self, key_id: str) -> None:
        """Call this when a previously rate-limited key succeeds again."""
        await self.session.execute(
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(status=KeyStatus.ACTIVE, cooldown_until=None)
        )
        await self.session.commit()
