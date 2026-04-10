import hashlib
from uuid import uuid4
from cryptography.fernet import Fernet

from db.models import APIKey, KeyStatus
from db.repositories.api_key import APIKeyRepository


MAX_FAILURES = 3

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

    async def get_key_for_use(self, provider: str) -> tuple[APIKey, str]:
        """Returns (model, decrypted_raw_key). Use raw_key to call the LLM."""
        keys = await self.repo.get_active_by_provider(provider)
        if not keys:
            raise RuntimeError(f"No active API keys for provider: {provider}")

        key = min(keys, key=lambda k: k.total_calls)
        raw_key = self.fernet.decrypt(key.encrypted_key.encode()).decode()
        return key, raw_key

    # --- Lifecycle ---

    async def on_failure(self, key_id: str) -> None:
        failures = await self.repo.increment_failure(key_id)
        if failures >= MAX_FAILURES:
            await self.repo.update_status(key_id, KeyStatus.INVALID)

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
        await self.repo.reset_failures(key_id)
        await self.repo.record_usage(key_id)