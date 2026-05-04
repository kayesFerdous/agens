from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import Settings


class SettingsRepository:
    """Data access layer for the Settings table (single-row, id=1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> Settings:
        """
        Return the settings row, creating it with defaults if missing.
        Never raises — safe to call on a fresh install.
        """
        result = await self._session.execute(
            select(Settings).where(Settings.id == 1)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = Settings(id=1, safety_mode=True)
            self._session.add(settings)
            await self._session.flush()

        return settings

    async def update(self, **kwargs) -> Settings:
        """
        Update settings fields by name. Flushes but does NOT commit.

        Args:
            **kwargs: Valid Settings column names → new values.
                      e.g. update(safety_mode=False)
        Raises:
            ValueError: If a key doesn't match any Settings field.
        """
        settings = await self.get()

        for key, value in kwargs.items():
            if not hasattr(settings, key):
                raise ValueError(f"Invalid settings field: {key!r}")
            setattr(settings, key, value)

        await self._session.flush()
        return settings
