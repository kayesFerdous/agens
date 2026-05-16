# agent/factory.py — constructs a fully-initialized Agent ready to call .chat() on
from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from agent.agent import Agent
from core.types import Usage
from db.repositories.api_key import APIKeyRepository
from core.registry import ToolRegistry
from llm.client import LLMClient
from llm.errors import LLMUnavailableError
from llm.providers import PROVIDER_DEFAULTS, build_provider_config
from config.settings import settings
from config.config_manager import ConfigManager
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool
from tools.search_web import WebSearchTool
from tools.schedule_add import ScheduleAddTool
from tools.schedule_delete import ScheduleDeleteTool
from tools.schedule_list import ScheduleListTool
from tools.schedule_update import ScheduleUpdateTool
from tools.update_config import UpdateConfigTool
from tools.find import FindTool
from tools.grep import GrepTool
from tools.list_directory import ListDirectoryTool



def _build_registry(
    config_manager: ConfigManager,
    usage: Usage,
    fernet: Fernet,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(FindTool())
    registry.register(ShellCommandTool(workspace_root=settings.WORKSPACE_ROOT))
    registry.register(GrepTool(workspace_root=settings.WORKSPACE_ROOT))
    registry.register(ListDirectoryTool(workspace_root=settings.WORKSPACE_ROOT))
    registry.register(ScheduleAddTool())
    registry.register(ScheduleListTool())
    registry.register(ScheduleDeleteTool())
    registry.register(ScheduleUpdateTool())

    # WebSearchTool resolves its own key per call — only fernet is needed at construction.
    registry.register(WebSearchTool(fernet, usage=usage))

    registry.register(UpdateConfigTool(config_manager))
    return registry


async def build_agent(session: AsyncSession) -> Agent:
    """Build and return one Agent instance to be shared across all interfaces.

    Args:
        session: A short-lived AsyncSession used *only* during startup to fetch
                 the initial API key.  The agent opens its own sessions per call.

    The agent stores fernet internally; callers never receive it separately.
    """
    fernet = Fernet(settings.FERNET_SECRET)
    usage = Usage()
    config_manager = ConfigManager()

    repo = APIKeyRepository(session)
    provider_name = getattr(settings, "DEFAULT_PROVIDER", "gemini")
    default_model = getattr(settings, "DEFAULT_MODEL", "") or PROVIDER_DEFAULTS[provider_name]["default_model"]
    key = await repo.pick_available_key(provider=provider_name, model=default_model)
    if key is None:
        raise LLMUnavailableError(
            f"No API keys found for provider '{provider_name}'. Add one with: agens apikey add"
        )
    raw_key = fernet.decrypt(key.encrypted_key.encode()).decode()

    registry = _build_registry(config_manager, usage, fernet)

    config = build_provider_config(provider_name, api_key=raw_key, model=default_model)
    llm = LLMClient(config)
    llm.current_key_id = key.id  # type: ignore[attr-defined]

    return Agent(
        registry=registry,
        llm=llm,
        config_manager=config_manager,
        fernet=fernet,
    )
