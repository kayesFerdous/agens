import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from cryptography.fernet import Fernet

from db.models import APIKey, KeyStatus
from db.repositories.api_key import APIKeyRepository


SHORT_COOLDOWN = 60        # fallback for minute-level limits with no header
DAY_IN_SECONDS = 86400

class APIKeyManager:

    def __init__(self, repo: APIKeyRepository, fernet: Fernet):
        self.repo = repo
        self.fernet = fernet

    # --- Write ---

    async def add_key(self, raw_key: str, provider: str, label: str | None = None) -> APIKey:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        if await self.repo.get_by_hash(key_hash):
            raise ValueError("This API key already exists.")

        api_key = APIKey(
            id=uuid4().hex,
            provider=provider,
            label=label,
            encrypted_key=self.fernet.encrypt(raw_key.encode()).decode(),
            key_hash=key_hash,
            key_hint=f"{raw_key[:3]}...{raw_key[-4:]}",
        )
        return await self.repo.insert(api_key)

    # --- Read ---

    @staticmethod
    def _last_used_sort_value(key: APIKey) -> float:
        if key.last_used_at is None:
            return float("-inf")

        last_used = key.last_used_at
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)
        return last_used.timestamp()

    async def get_key_for_use(self, provider: str) -> tuple[APIKey, str]:
        """Returns (model, decrypted_raw_key). Use raw_key to call the LLM."""
        keys = await self.repo.get_active_by_provider(provider)
        if not keys:
            raise RuntimeError(f"No active API keys for provider: {provider}")

        # Prefer never-used keys first, then the least recently used key.
        key = min(keys, key=self._last_used_sort_value)
        raw_key = self.fernet.decrypt(key.encrypted_key.encode()).decode()
        return key, raw_key

    async def is_key_usable_now(self, key_id: str | None, provider: str) -> bool:
        if not key_id:
            return False
        await self.repo.check_cooldown(provider=provider)
        return await self.repo.is_key_usable_now(key_id=key_id, provider=provider)

    async def is_model_available_for_key(self, key_id: str, model: str) -> bool:
        key = await self.repo.get_by_id(key_id)

        if key: 
            if not key.model_cooldowns:
                return True
            entry = key.model_cooldowns.get(model)
            if not entry or entry.get("until") is None:
                return True
            if datetime.fromisoformat(entry["until"]) <= datetime.now(timezone.utc):
                await self.repo.clear_model_cooldown(key, model) 
                return True

            return False
        return False

    # --- Lifecycle ---

    async def on_failure(self, key_id: str) -> None:
        # Failure counters were removed from the schema; keep this for API compatibility.
        await self.repo.increment_failure(key_id)

    async def deactivate(self, key_id: str) -> None:
        await self.repo.update_status(key_id, KeyStatus.INACTIVE)



    async def on_rate_limit(
        self, key_id: str, retry_after: int | None = None, is_daily: bool = False
    ) -> None:
        if is_daily:
            # No point retrying today — mark exhausted until tomorrow
            await self.repo.set_cooldown(key_id, DAY_IN_SECONDS, status=KeyStatus.EXHAUSTED)
        else:
            seconds = retry_after or SHORT_COOLDOWN
            await self.repo.set_cooldown(key_id, seconds, status=KeyStatus.RATE_LIMITED)

    async def on_success(self, key_id: str) -> None:
        await self.repo.clear_cooldown(key_id)   # revive if it was rate-limited
        await self.repo.record_usage(key_id)
