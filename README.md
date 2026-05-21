<div align="center">

<img src="frontend/src/assets/logo.svg" alt="Agens Logo" width="180" />

# Agens

**An interface-agnostic AI agent platform that executes complex system-level and web tasks through a centralized ReAct orchestration engine.**

[![PyPI](https://img.shields.io/badge/pypi-placeholder-blue?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/agens/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](./LICENSE)
[![Interfaces](https://img.shields.io/badge/interfaces-CLI%20%7C%20TUI%20%7C%20Web%20%7C%20Telegram-f97316?style=flat-square)](#interface-overview)

</div>

---

Agens decouples stateful AI reasoning from delivery channels. A centralized agent engine (`agent.py`) coordinates session histories, tool execution routing, and provider-fallback logic — exposing a unified interface to thin transport-layer adapters. All client interfaces share the same SQLite database, memory, and configuration with zero context drift.

> **Agens is completely free to use.** The platform itself costs nothing — you only need a personal API key from any supported provider (Gemini, OpenAI, Groq, Cerebras, SiliconFlow, DeepSeek).

---

## Why Agens?

*   🧠 **Centralized Intelligence**: Decoupled Ports & Adapters (Hexagonal) architecture. All client interfaces share a single database, settings, and memories with zero context drift.
*   🔒 **Zero-Trust Key Security**: API keys are Fernet-encrypted at rest and decrypted purely in-memory. They are never saved in plaintext configuration files.
*   🔄 **Automatic Rate-Limit Cooldown**: Transparent key rotation and failover. If an API key hits a `429 Rate Limit`, Agens automatically shifts to the next available key and retries the request seamlessly.
*   🌐 **Free Native Tools**: Built-in DuckDuckGo web search and HTML page retrieval — zero external paid search API subscriptions required.
*   🛡️ **Layered Safety Controls**: Built-in Safety Mode gates dangerous subprocess executions, while local Textual TUI collects `sudo` credentials securely on-the-fly.

---

## 📚 Documentation Hub

Explore the detailed technical manuals and operational guides:

*   🚀 **[Installation & Setup](docs/installation.md)**: Native and containerized setups across Linux, macOS, and Windows.
*   🏗️ **[Architecture Deep Dive](docs/architecture.md)**: Learn about the Hexagonal Ports & Adapters layout, the ReAct stream loop, and key database connection designs.
*   🛠️ **[Tool System & Custom Tools](docs/tools.md)**: Explore the core tool directory, layered safety rules, and step-by-step custom tool development tutorials.
*   ⚙️ **[Configuration & Key Management](docs/configuration.md)**: Deep dive into environments, user memory settings, encrypted API credentials, and automatic rate-limit cooldown algorithms.
*   💻 **[Developer & Contributor Manual](docs/development.md)**: Workspace setup guides, release packaging commands, custom interface implementation, and open-source contribution rules.

---

## Quick Start

### 1. Install Agens
```bash
pipx install agens
```

### 2. Register an API Key
```bash
agens apikey add my-gemini gemini AIzaSyB...
```

### 3. Launch an Interface
```bash
agens web                                              # Web UI (Svelte 5) → http://localhost:8000
agens tui                                             # Terminal UI Dashboard (Textual)
agens chat "List the contents of my workspace"        # Single-line Typer CLI query
```

---

## Interface Overview

All interface adapters communicate with the exact same central brain and write to the same database. Prompt behavior and safety policies dynamically adjust depending on the interface:

| Interface | Launch Command | Core Capabilities | Concurrency Model |
| :--- | :--- | :--- | :--- |
| **CLI** | `agens chat "<msg>"` | One-shot queries, API key administration, safety overrides | Ephemeral process; runs one ReAct loop and exits |
| **Terminal UI (TUI)** | `agens tui [--session <id>]` | Interactive Textual dashboard, session loading, inline `sudo` password collection | Stateful Textual app; blocks terminal during execution |
| **Web UI** | `agens web` | Svelte 5 + FastAPI SPA with SSE streaming, model picker, tool status blocks | Client-server; tokens stream live via Server-Sent Events |
| **Telegram Bot** | `agens telegram` | Remote message-based assistant via `python-telegram-bot`, polling + webhooks | Long-polling or webhook updater; edits messages sequentially to stay within Telegram rate limits |

---

## Architecture Diagram

```mermaid
graph TD
    Input["User Input<br/>(Web · TUI · Telegram · CLI)"]
    Adapter["Interface Adapter<br/>src/interfaces/"]
    Agent["Agent Orchestrator<br/>src/agent/agent.py"]
    DB[("Local SQLite<br/>src/db/")]
    PromptBuilder["Prompt Builder<br/>src/planner/prompt_builder.py"]
    LLMClient["LLM Client & Router<br/>src/llm/"]
    ToolRegistry["Tool Registry<br/>src/core/registry.py"]
    Tools["Tool Execution<br/>src/tools/"]

    Input -->|triggers| Adapter
    Adapter -->|".chat(message, session_id, channel)"| Agent
    Agent -->|loads session history| DB
    Agent -->|requests system prompt| PromptBuilder
    PromptBuilder -->|reads settings & memories| DB
    Agent -->|invokes ReAct loop| LLMClient
    LLMClient -->|"chunks / tool_calls"| Agent
    Agent -->|routes tool call| ToolRegistry
    ToolRegistry -->|executes| Tools
    Tools -->|returns result dict| Agent
    Agent -->|"yields StreamEvent"| Adapter
    Adapter -->|renders live output| Input
```

---

## License

Agens is distributed under the [MIT License](LICENSE).
