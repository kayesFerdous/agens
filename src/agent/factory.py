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
# from llm.api_key_manager import APIKeyManager
from services.api_key_manager import APIKeyManager
from config.settings import settings
from config.config_manager import ConfigManager
# from tools.find_directory import FindDirectoryTool
# from tools.find_file import FindFileTool
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

# Shared API key manager instance for the application
_key_manager: APIKeyManager | None = None



def build_registry(config_manager: ConfigManager, usage: Usage, api_key: str) -> ToolRegistry:
    registry = ToolRegistry()
    # registry.register(FindDirectoryTool())
    # registry.register(FindFileTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(FindTool())
    registry.register(ShellCommandTool(workspace_root=settings.WORKSPACE_ROOT))
    registry.register(GrepTool(workspace_root=settings.WORKSPACE_ROOT))
    registry.register(ListDirectoryTool(workspace_root=settings.WORKSPACE_ROOT))

    # Dedicated client for web search — uses first available key
    search_client = genai.Client(api_key=api_key)
    registry.register(WebSearchTool(search_client, usage=usage))

    # Config management
    registry.register(UpdateConfigTool(config_manager))

    return registry


async def build_agent(session: AsyncSession, fernet: Fernet) -> Agent:
    usage = Usage()
    config_manager = ConfigManager(_CONFIG_PATH)
    repo = APIKeyRepository(session)
    keys = APIKeyManager(repo, fernet=fernet)
    key, raw_key = await keys.get_key_for_use("gemini") #TODO: make it automatic
    registry = build_registry(config_manager, usage, api_key=raw_key)

    # Create LLM with key manager for automatic rotation
    llm = GeminiLLM(
        usage=usage,
        client=genai.Client(api_key=raw_key),
        current_key_id=key.id,
    )
    return Agent(registry=registry, llm=llm, config_manager=config_manager)
