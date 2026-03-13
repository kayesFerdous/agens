# agent/factory.py — wires up the Agent with its dependencies
from agent.agent import Agent
from planner.planner import Planner
from core.registry import ToolRegistry
from llm.gemini import GeminiLLM
from config.settings import settings
from tools.file_search import FileSearchTool
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FileSearchTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(ShellCommandTool())
    return registry


def build_agent() -> Agent:
    registry = build_registry()
    llm = GeminiLLM(model=settings.DEFAULT_MODEL, api_key=settings.GOOGLE_API_KEY)
    planner = Planner(llm=llm, tool_descriptions=registry.tool_descriptions())
    return Agent(planner=planner, registry=registry)
