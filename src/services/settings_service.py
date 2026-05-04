from sqlalchemy.ext.asyncio import AsyncSession
from db.repositories.settings import SettingsRepository
from db.models import Settings


class SettingsService:
    """Owns the transaction boundary for settings reads and writes."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SettingsRepository(session)
        self._session = session

    async def get_settings(self) -> Settings:
        """Return current settings. Created with defaults if first run."""
        return await self._repo.get()

    async def update_settings(self, **kwargs) -> Settings:
        """
        Update and commit settings in one call.

        Args:
            **kwargs: Fields to change. e.g. update_settings(safety_mode=True)
        Returns:
            The committed Settings instance.
        Raises:
            ValueError: If any key is not a valid Settings field.
        """
        settings = await self._repo.update(**kwargs)
        await self._session.commit()
        return settings
