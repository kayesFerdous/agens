# agent/factory.py — wires up the Agent with its dependencies
from google import genai

from agent.agent import Agent
from memory.manager import MemoryManager
from core.registry import ToolRegistry
from llm.gemini import GeminiLLM
from config.settings import settings
from tools.find_directory import FindDirectoryTool
from tools.find_file import FindFileTool
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool
from tools.search_web import WebSearchTool


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FindDirectoryTool())
    registry.register(FindFileTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(ShellCommandTool())

    # Dedicated client for web search — isolated from the agent's main LLM
    search_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    registry.register(WebSearchTool(search_client))

    return registry


def build_agent() -> Agent:
    registry = build_registry()
    llm = GeminiLLM(model=settings.DEFAULT_MODEL, api_key=settings.GOOGLE_API_KEY)
    memory_manager = MemoryManager()
    return Agent(registry=registry, llm=llm, memory_manager=memory_manager)
