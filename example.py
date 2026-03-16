# example.py — demonstrates full Agent -> Planner -> Tool -> Result flow
# Uses a fake LLM so this runs without an API key.
import json
from config.logging import setup_logging
from llm.base import LLM, ReactResult
from core.types import ToolCall
from core.registry import ToolRegistry
from agent.agent import Agent
from tools.find_file import FindFileTool
from tools.file_read import FileReadTool
from tools.file_edit import FileEditTool

setup_logging()


class FakeLLM(LLM):
    """A fake LLM that executes a hardcoded ReAct loop."""
    def __init__(self, plan: list[ToolCall]) -> None:
        self._plan = plan

    def generate(self, prompt: str, *, system: str = "", temperature: float = 0) -> str:
        return "Not implemented"

    def generate_structured(self, prompt: str, *, system: str = "", temperature: float = 0, response_schema: dict | None = None) -> str:
        return "{}"

    def generate_stream(self, prompt: str, *, system: str = "", temperature: float = 0):
        yield "Not implemented"

    def react(self, user_request: str, *, system: str = "", tool_schemas: list[dict], tool_executor, max_iterations: int = 10, temperature: float = 0) -> ReactResult:
        history = []
        for step in self._plan:
            try:
                result = tool_executor(step.tool, step.arguments)
                step.result = result
            except Exception as e:
                step.error = str(e)
            history.append(step)
        return ReactResult(answer="I have fixed the typo for you.", tool_calls=history)


def main() -> None:
    # --- Setup: create a temp file with a typo ---
    import tempfile, os
    from pathlib import Path
    import config.workspace
    
    tmpdir = tempfile.mkdtemp()
    bad_file = os.path.join(tmpdir, "main.py")
    with open(bad_file, "w") as f:
        f.write('if __name__ == "__main__":\n    prin("hello world")\n')

    # Mock the workspace root so tools allow paths inside tmpdir
    config.workspace.WORKSPACE_ROOT = Path(tmpdir).resolve()

    print(f"Created test file: {bad_file}")
    print(f"Before:\n{open(bad_file).read()}")

    # --- The hardcoded steps the LLM would take ---
    hardcoded_plan = [
        ToolCall(tool="find_file", arguments={"directory": tmpdir, "pattern": "main.py"}),
        ToolCall(tool="read_file", arguments={"path": bad_file}),
        ToolCall(tool="edit_file", arguments={"path": bad_file, "find": "prin(", "replace": "print("}),
    ]

    # --- Wire up ---
    registry = ToolRegistry()
    registry.register(FindFileTool())
    registry.register(FileReadTool())
    registry.register(FileEditTool())

    llm = FakeLLM(plan=hardcoded_plan)
    agent = Agent(registry=registry, llm=llm)

    # --- Execute ---
    response = agent.run("Fix the typo prin( -> print( in main.py")

    # --- Report ---
    print("\n=== Results ===")
    print("Answer:", response.answer)
    for i, call in enumerate(response.tool_history, 1):
        status = "FAIL" if call.error else "OK"
        print(f"  [{i}] [{status}] {call.tool}: {call.result or call.error}")

    print(f"\nAfter:\n{open(bad_file).read()}")

    # Cleanup
    os.remove(bad_file)
    os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
