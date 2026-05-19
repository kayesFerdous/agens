# llm/router.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet
from db.database import async_session
from db.repositories.api_key import APIKeyRepository
from llm.catalog import ModelEntry, get_catalog, get_fallback_chain, get_model
from llm.providers import build_provider_config
from llm.client import LLMClient

@dataclass
class BoundModel:
    entry: ModelEntry
    key_id: str
    client: LLMClient


def _find_catalog_entry(provider: str, model_id: str) -> ModelEntry | None:
    for entry in get_catalog():
        if entry.provider == provider and entry.id == model_id:
            return entry
    return None

class FreeTierRouter:
    """
    Picks the next best free-tier model + key combo.
    Stateless: relies on api_key.model_cooldowns for exclusion logic.
    """

    def __init__(self, fernet: Fernet):
        self._fernet = fernet
        self._chain = get_fallback_chain()

    async def pick_next(
        self,
        preferred: str | None = None,
        exclude: set[str] | None = None,
    ) -> Optional[BoundModel]:
        """
        preferred: exact model id or provider/model id requested by user (optional).
        exclude:   model ids currently cooling down.
        """
        candidates: list[ModelEntry] = []
        if preferred:
            if "/" in preferred:
                preferred_provider, preferred_model = preferred.split("/", maxsplit=1)
                p = _find_catalog_entry(preferred_provider, preferred_model)
            else:
                p = get_model(preferred)
            if p:
                candidates.append(p)
        candidates += [c for c in self._chain if c not in candidates]

        async with async_session() as session:
            repo = APIKeyRepository(session)
            excluded = exclude or set()
            for entry in candidates:
                if entry.id in excluded:
                    continue
                key = await repo.pick_available_key(entry.provider, entry.id)
                if key is None:
                    continue
                raw = self._fernet.decrypt(key.encrypted_key.encode()).decode()
                config = build_provider_config(entry.provider, raw, entry.id)
                # Override per-model parallel_tool_calls from catalog
                config.parallel_tool_calls = entry.parallel_tool_calls
                return BoundModel(
                    entry=entry,
                    key_id=key.id,
                    client=LLMClient(config),
                )
        return None
