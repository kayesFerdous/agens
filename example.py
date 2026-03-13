# example.py — demonstrates full Agent -> Planner -> Tool -> Result flow
# Uses a fake LLM so this runs without an API key.
import json
import logging
from llm.base import LLM
from core.registry import ToolRegistry
from planner.planner import Planner
from agent.agent import Agent
from tools.file_search import FileSearchTool
from tools.file_read import FileReadTool
from tools.file_edit import FileEditTool

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


class FakeLLM(LLM):
    # Returns a hardcoded plan for the typo-fix scenario.
    def __init__(self, plan: list[dict]) -> None:  # type: ignore[type-arg]
        self._plan = plan

    def generate(self, prompt: str, system: str = "") -> str:
        return json.dumps(self._plan)


def main() -> None:
    # --- Setup: create a temp file with a typo ---
    import tempfile, os
    tmpdir = tempfile.mkdtemp()
    bad_file = os.path.join(tmpdir, "main.py")
    with open(bad_file, "w") as f:
        f.write('if __name__ == "__main__":\n    prin("hello world")\n')

    print(f"Created test file: {bad_file}")
    print(f"Before:\n{open(bad_file).read()}")

    # --- The plan the LLM would produce ---
    hardcoded_plan = [
        {"tool": "search_file", "arguments": {"path": tmpdir, "pattern": "main.py"}},
        {"tool": "read_file", "arguments": {"path": bad_file}},
        {"tool": "edit_file", "arguments": {"path": bad_file, "find": "prin(", "replace": "print("}},
    ]

    # --- Wire up ---
    registry = ToolRegistry()
    registry.register(FileSearchTool())
    registry.register(FileReadTool())
    registry.register(FileEditTool())

    llm = FakeLLM(plan=hardcoded_plan)
    planner = Planner(llm=llm, tool_names=registry.list_tools())
    agent = Agent(planner=planner, registry=registry)

    # --- Execute ---
    response = agent.run("Fix the typo prin( -> print( in main.py")

    # --- Report ---
    print("\n=== Results ===")
    for r in response.results:
        status = "OK" if r.success else "FAIL"
        print(f"  [{status}] {r.step.tool}: {r.output[:120]}")

    print(f"\nAfter:\n{open(bad_file).read()}")

    # Cleanup
    os.remove(bad_file)
    os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
