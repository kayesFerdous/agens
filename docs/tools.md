# Tool System & Custom Tools

[Home (README)](../README.md) · [Architecture Deep Dive](architecture.md) · [Installation & Setup](installation.md) · [Configuration](configuration.md) · [Developer Manual](development.md)

---

Agens uses what is called a **ReAct loop** (Reasoning and Acting). Think of it as a simple cycle:
1. You ask Agens a question.
2. The brain decides if it needs a tool (like searching the web or opening a file).
3. It runs the tool, reads the result, and continues thinking.
4. It repeats this until it has a final answer for you.

This guide explains what built-in tools Agens has, how we keep your system safe, and how you can write your own custom tools in just a few lines of Python.

---

## 🛠️ Built-in Tool Directory

By default, Agens comes with a suite of robust, pre-installed tools. You do **not** need to pay for any search APIs (like Google or Bing) to look up facts—everything is completely free out-of-the-box.

| Tool | What it does | Simple Explanation |
| :--- | :--- | :--- |
| `file_read` | **Read Files** | Reads the contents of any text file inside your workspace. |
| `file_write` | **Create Files** | Creates new files or completely writes over existing ones. |
| `file_edit` | **Edit Files** | Safely replaces specific blocks of text in a file. |
| `list_directory` | **List Directory** | Shows all files and folders in your active workspace. |
| `find` | **Find Files** | Searches for files by their name or size. |
| `grep` | **Search Text** | Looks for specific words or patterns inside your files. |
| `shell_command` | **Run Shell** | Executes terminal commands directly on your computer. |
| `web_search` | **Search Web** | Searches DuckDuckGo for live facts and fresh news. |
| `web_fetch` | **Read Webpage** | Downloads any webpage and converts it to clean, readable markdown. |
| `update_config` | **Save Memories** | Remembers facts about you (like your location or coding style). |
| `schedule_add` | **Add Reminder** | Saves custom reminders and calendar events. |
| `schedule_list` | **View Calendar** | Lists all your upcoming alerts and scheduled events. |
| `schedule_delete`| **Delete Event** | Removes a reminder or calendar alert. |

---

## 🛡️ Layered Safety & Sudo Policies

Because Agens is powerful and can run terminal commands via `shell_command`, we enforce strict safety rules to protect your system.

### 1. Safety Mode
Safety Mode is a smart gatekeeper that is turned **ON** by default. 
- It automatically inspects terminal commands before they run.
- It immediately blocks dangerous patterns (like recursive system deletions or modifications to core OS folders).
- You can turn it on or off easily from your terminal:
  ```bash
  agens safety on
  agens safety off
  ```

Alternatively, you can toggle Safety Mode or enable/disable specific tool groups visually using the Svelte Web UI settings dashboard:

<div align="center">
  <img src="../assets/web-tool-group.png" alt="Tool Safety Panel" width="550" style="border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);" />
</div>

### 2. Interface-Aware Sudo Policies
The brain is smart enough to know where your requests are coming from:
*   **Terminal UI (TUI)**: The local TUI is trusted because you are running it directly. If a command needs `sudo` access, the TUI will pause and pop up a secure box to collect your password. This password is sent directly to the process in-memory and is **never** saved to disk or printed in any log files.
*   **Web Dashboard & Telegram**: These channels are considered untrusted/remote. Agens **hard-blocks** all privileged `sudo` requests coming from these interfaces to prevent remote hacker attacks.

---

## 🔌 Tutorial: Writing Your Own Custom Tool

Adding custom tools to Agens is incredibly simple. All you have to do is write a small Python subclass and register it.

### Step 1: Create a Python file
Create a new file under `src/tools/` (e.g., `src/tools/my_stats.py`) and subclass our base `Tool` class.

### Step 2: Define your metadata and Schema
Provide a simple `name`, a plain-English `description` (so the AI knows when to use it), and a JSON schema describing what arguments it accepts.

### Step 3: Implement your execution logic
Write a simple `execute` method that does the actual work. Agens handles the rest (including running blocking tasks in background threads so your interface never freezes).

### Step 4: Register your tool
Open `src/agent/factory.py` and register your new tool class in the `_build_registry` method:
```python
# src/agent/factory.py
from tools.my_stats import MyStatsTool

def _build_registry(self) -> ToolRegistry:
    registry = ToolRegistry()
    # Existing tool registrations...
    registry.register(MyStatsTool()) # Add this line!
    return registry
```

---

### Complete Copy-Pasteable Template

Here is a simple custom tool that reads system disk space and OS version:

```python
# src/tools/my_stats.py
from __future__ import annotations
import shutil
import platform
from typing import Any
from core.tool_interface import Tool


class MyStatsTool(Tool):
    """A simple tool to fetch local computer statistics."""

    @property
    def name(self) -> str:
        # The unique ID used by the model
        return "get_system_stats"

    @property
    def description(self) -> str:
        # Tell the model when it should use this tool
        return "Fetches fundamental system details, including active OS information and total disk space statistics."

    @property
    def parameters(self) -> dict:
        # Define what inputs this tool expects (uses standard JSON Schema)
        return {
            "type": "object",
            "properties": {
                "include_disk": {
                    "type": "boolean",
                    "description": "If true, fetches total and free disk space for the root drive.",
                }
            },
            "required": [],
        }

    def execute(self, **kwargs: Any) -> dict:
        # The main code that runs when the model invokes this tool
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

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🚀 **[Installation & Setup](installation.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- ⚙️ **[Configuration & Key Management](configuration.md)**
- 💻 **[Developer & Contributor Manual](development.md)**
