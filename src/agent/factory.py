# agent/factory.py — constructs a fully-initialized Agent ready to call .chat() on
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from agent.agent import Agent
from core.types import Usage
from db.repositories.api_key import APIKeyRepository
from memory.manager import MemoryManager
from core.registry import ToolRegistry
from llm.gemini import GeminiLLM
from services.api_key_manager import APIKeyManager
from config.settings import settings
from config.config_manager import ConfigManager
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool
from tools.search_web import WebSearchTool
from tools.update_config import UpdateConfigTool
from tools.find import FindTool
from tools.grep import GrepTool
from tools.list_directory import ListDirectoryTool


# Canonical path for the assistant's config file.
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"


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
    config_manager = ConfigManager(_CONFIG_PATH)

    repo = APIKeyRepository(session)
    key_manager = APIKeyManager(repo, fernet=fernet)
    key, raw_key = await key_manager.get_key_for_use("gemini")  # TODO: multi-provider

    # One shared genai.Client for both the LLM and the web-search tool.
    shared_client = genai.Client(api_key=raw_key)

    registry = _build_registry(config_manager, usage, fernet)

    llm = GeminiLLM(
        usage=usage,
        client=shared_client,
        current_key_id=key.id,
    )

    return Agent(
        registry=registry,
        llm=llm,
        config_manager=config_manager,
        fernet=fernet,
    )
