# main.py — entry point
import logging
from agent.agent import Agent
from planner.planner import Planner
from core.registry import ToolRegistry
from llm.gemini import GeminiLLM
from config.settings import DEFAULT_MODEL
from tools.file_search import FileSearchTool
from tools.file_read import FileReadTool
from tools.file_write import FileWriteTool
from tools.file_edit import FileEditTool
from tools.shell_command import ShellCommandTool

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


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
    llm = GeminiLLM(model=DEFAULT_MODEL)
    planner = Planner(llm=llm, tool_names=registry.list_tools())
    return Agent(planner=planner, registry=registry)


def main() -> None:
    agent = build_agent()
    request = input("Request: ")
    response = agent.run(request)

    if response.success:
        print("\nDone. All steps succeeded.")
    else:
        print(f"\nFailed: {response.error}")

    for r in response.results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.step.tool}: {r.output[:120]}")


if __name__ == "__main__":
    main()
