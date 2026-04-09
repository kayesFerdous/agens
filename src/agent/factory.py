# agent/factory.py — wires up the Agent with its dependencies
from pathlib import Path

from google import genai

from agent.agent import Agent
from core.types import Usage
from memory.manager import MemoryManager
from core.registry import ToolRegistry
from llm.gemini import GeminiLLM
from llm.api_key_manager import APIKeyManager
from config.settings import settings
from config.config_manager import ConfigManager
from tools.find_directory import FindDirectoryTool
from tools.find_file import FindFileTool
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool
from tools.search_web import WebSearchTool
from tools.update_config import UpdateConfigTool


# Canonical path for the assistant's config file.
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"

# Shared API key manager instance for the application
_key_manager: APIKeyManager | None = None


def get_key_manager() -> APIKeyManager:
    """Get or create the shared API key manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = APIKeyManager(
            api_keys=settings.get_api_keys(),
            rate_limit_cooldown=settings.RATE_LIMIT_COOLDOWN,
            quota_exhausted_cooldown=settings.QUOTA_EXHAUSTED_COOLDOWN,
        )
    return _key_manager


def build_registry(config_manager: ConfigManager, usage: Usage) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FindDirectoryTool())
    registry.register(FindFileTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(ShellCommandTool())

    # Dedicated client for web search — uses first available key
    key_manager = get_key_manager()
    search_client = genai.Client(api_key=key_manager.get_available_key())
    registry.register(WebSearchTool(search_client, usage=usage))

    # Config management
    registry.register(UpdateConfigTool(config_manager))

    return registry


def build_agent() -> Agent:
    usage = Usage()
    config_manager = ConfigManager(_CONFIG_PATH)
    registry = build_registry(config_manager, usage)

    # Create LLM with key manager for automatic rotation
    key_manager = get_key_manager()
    llm = GeminiLLM(
        usage=usage,
        model=settings.DEFAULT_MODEL,
        key_manager=key_manager,
    )
    return Agent(registry=registry, llm=llm, config_manager=config_manager)
