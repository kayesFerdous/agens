# Tool System & Custom Tools

Agens leverages an autonomous **ReAct (Reasoning and Acting) execution loop**. The model is provided with a registry of tools and can choose to execute them, receive the results, and continue reasoning.

This guide outlines the available tools in the platform, the layered security model that controls their execution, and a step-by-step tutorial on building custom tool extensions.

---

## Core Tool Directory

Agens includes a native suite of highly resilient tools. By default, it requires zero external API subscriptions (like paid search keys) to perform comprehensive operations:

| Tool | Purpose | Destructive | Restrictions |
| :--- | :--- | :---: | :--- |
| `file_read` | Read file contents in the active workspace | — | Scoped strictly to `WORKSPACE_ROOT` |
| `file_write` | Create or overwrite files | ✓ | Scoped strictly to `WORKSPACE_ROOT` |
| `file_edit` | Perform target string-match edits on files | ✓ | Scoped strictly to `WORKSPACE_ROOT`; requires exact string matching |
| `list_directory` | List files and directories | — | Scoped strictly to `WORKSPACE_ROOT` |
| `find` | Find files matching specific name or size filters | — | Scoped strictly to `WORKSPACE_ROOT` |
| `grep` | Pattern-match text within workspace files | — | Scoped strictly to `WORKSPACE_ROOT` |
| `shell_command` | Execute shell commands in a host subprocess | ✓ | Controlled by Safety Mode; restricted commands are hard-blocked; `sudo` restricted |
| `web_search` | Query DuckDuckGo for live facts and news | — | No external API key required; rate-limited retry support |
| `web_fetch` | Download and convert raw HTML from any web URL to clean markdown | — | Parses web pages securely |
| `update_config` | Deep-merge memory entries into `config.json` | ✓ | Scopes changes to the `user.memories` namespace; supports memory deletion |
| `schedule_add` | Add calendar event records to the DB | — | Writes to the SQLite `schedule_events` table |
| `schedule_list` | Read active calendar events | — | Reads from SQLite |
| `schedule_update` | Update calendar event dates or descriptions | — | Writes to SQLite |
| `schedule_delete` | Remove a calendar event | ✓ | Deletes from SQLite |

---

## Layered Safety & Authorization Model

Because Agens is capable of executing host-level commands via `shell_command`, it enforces a multi-tiered security model to protect user environments.

### 1. Safety Mode (`SAFETY_MODE_ENABLED`)
Safety Mode is a hard gate enforced directly inside the orchestrator. When enabled (default: `True`), it:
- Blocks destructive commands (e.g., recursive deletes on system dirs, modifications to core OS files).
- Rejects dangerous shell patterns (such as chaining arbitrary command executions).
- Toggled globally using the CLI:
  ```bash
  agens safety on
  agens safety off
  ```

Alternatively, you can manage active tool groups, customize capabilities, and toggle Safety Mode dynamically from the premium Svelte Web UI settings dashboard:

<div align="center">
  <p><b>Web UI Tool Settings & Safety Controls:</b></p>
  <img src="../assets/web-tool-group.png" alt="Web Tool Group & Safety Controls" width="600" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);" />
</div>

### 2. Interface-Aware Sudo Policies
The LLM system prompt is channel-aware. Safety directives and sudo privileges adapt dynamically depending on the active interface transport:

*   **Terminal UI (TUI)**: The local TUI is considered a highly trusted direct interface. When a privileged command requires `sudo` (and safety is off):
    1. Agens suspends generation stream rendering.
    2. A secure modal widget (`SudoPasswordPrompt`) is presented.
    3. The collected password is fed directly to the subprocess via stdin (without ever storing it, saving it to disk, or outputting it in log files).
*   **Web UI & Telegram**: These channels are considered untrusted or remote. Agens **hard-blocks** all privileged `sudo` execution requests and replies with a secure rejection explaining that `sudo` commands must be initiated locally from the TUI adapter.

---

## Tutorial: Building a Custom Tool

Adding custom tools to Agens is designed to be plug-and-play. The framework automatically parses your tool's JSON schema and handles both synchronous and asynchronous execution.

### Step 1: Subclass the base Tool interface
Create a new file under `src/tools/your_tool.py` and subclass the base `Tool` class.

### Step 2: Define metadata and the JSON Schema
You must implement `name`, `description`, and the `parameters` JSON Schema dict. These are fed directly to LLM provider function-calling APIs.

### Step 3: Implement execution logic
Implement the `execute(self, **kwargs)` method.
- **Sync Support**: If your tool logic is synchronous, write a standard `def execute(self, **kwargs)`. The orchestrator will automatically execute it inside `asyncio.to_thread()` to prevent blocking the async event loop.
- **Async Support**: If your tool uses async operations, write an `async def execute(self, **kwargs)` coroutine. The orchestrator will detect this and `await` it directly.

### Complete Copy-Pasteable Template

Here is a concrete example of a custom tool that fetches system statistics:

```python
# src/tools/system_stats.py
from __future__ import annotations
import shutil
import platform
from typing import Any
from core.tool_interface import Tool


class SystemStatsTool(Tool):
    """Retrieve local system metrics such as disk space and OS version."""

    @property
    def name(self) -> str:
        return "get_system_stats"

    @property
    def description(self) -> str:
        return "Fetches fundamental system details, including active OS information and total disk space statistics."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "include_disk": {
                    "type": "boolean",
                    "description": "If true, fetches total, used, and free disk space for the root partition.",
                }
            },
            "required": [],
        }

    def execute(self, **kwargs: Any) -> dict:
        include_disk: bool = kwargs.get("include_disk", True)
        
        stats = {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
        }
        
        if include_disk:
            total, used, free = shutil.disk_usage("/")
            stats["disk"] = {
                "total_gb": round(total / (2**30), 2),
                "used_gb": round(used / (2**30), 2),
                "free_gb": round(free / (2**30), 2),
            }
            
        return stats
```

### Step 4: Register your tool
Open `src/agent/factory.py` and register your new tool class in the `_build_registry` method:

```python
# src/agent/factory.py
from tools.system_stats import SystemStatsTool

def _build_registry(self) -> ToolRegistry:
    registry = ToolRegistry()
    # Existing tool registrations...
    registry.register(SystemStatsTool()) # Register your custom tool
    return registry
```

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🚀 **[Installation & Setup](installation.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- ⚙️ **[Configuration & Key Management](configuration.md)**
- 💻 **[Developer & Contributor Manual](development.md)**
