# 1. Project Overview

Vela is a unified, multi-channel AI assistant platform designed to execute complex tasks asynchronously while communicating and maintaining state across a versatile array of interfaces. At its core, it is a backend agent framework with integrated capabilities to understand user intent, store memory context locally, and autonomously invoke various system-level or web-level tools (filesystem access, web search, shell execution) using a ReAct (Reason + Act) loop.

**Main Purpose and Core Idea**
The core philosophy of the application is **interface ubiquity with centralized brain logic**. Rather than building an agent locked into a terminal or a web app, the platform wraps one core agent orchestration layer around four distinct graphical/interaction channels (CLI, Terminal UI, Web UI, and Telegram). State, memory, database, and configurations are globally shared. 

**Main Workflow**
1. The user initiates the application via a highly robust CLI (`vela start web telegram`, `vela tui`).
2. The runtime spins up an asynchronous event loop running Uvicorn (Web), Textual (TUI), and/or Python-Telegram-Bot (Telegram integration).
3. The user inputs prompts into an interface. 
4. The interface converts the input into a standard format and proxies it to the `Agent`.
5. The `Agent` queries a local SQLite database for conversation history, formulates a system prompt using injected tooling schemas, and communicates with LLMs (primary Gemini, but structured to support OpenAI).
6. The LLM's response is streamed back simultaneously, with transparent interrupts for automatic tool execution.

**Target Audience**
This platform is designed for power users, developers, and autonomous system operators who need deeply integrated AI that can execute code, manipulate their filesystem, manage complex configurations, and be accessible remotely (Telegram) or locally (TUI/Web) without context gaps.

---

# Capabilities & Key Features
- **Free to Use**: The platform itself is entirely free. You just need a personal Gemini API key.
- **Resilient Key Management**: You can add multiple API keys. If one hits a rate limit, the system automatically switches to the next available key without interrupting your workflow.
- **Native Web Search**: The app uses Gemini's built-in Search Tool (Google Grounding, see `src/tools/search_web.py`), so there is no need to set up or pay for a dedicated web search API.
- **Beginner Friendly**: Despite its power, the interface is simple and straightforward—anyone can use it.
- **Safety Mode**: An optional safety mode requires manual confirmation (Sudo) for destructive commands, allowing users to leverage powerful shell tools without fear of accidental system damage.
- **Limitation**: Currently, the platform *only* supports Gemini as the core underlying model provider.

---

# 2. Complete Feature Analysis

### 2.1 Multi-Interface Unified Brain
*   **What it does:** Allows the user to communicate with the same intelligent agent utilizing the same database sessions via different frontends.
*   **How it works:** The interfaces are structured as thin "adapters". They share a single instance of `Agent` that isolates the logic from the transport layer. 
*   **Modules responsible:** main.py sets up the interface environments, `src/interfaces/(web|tui|telegram)` serve as routers, and agent.py processes streams logic.

### 2.2 ReAct Tool-Calling & Streaming Strategy
*   **What it does:** Executes AI workflows where the AI can think, pick a tool, observe the response, and answer. Output is streamed live to the user.
*   **How it works:** Handled via an `AsyncIterator[StreamEvent]`. The agent yields events (`StreamEvent(type="text", content="...")` or `StreamEvent(type="tool", ...)`). The web adapter streams these via Server-Sent Events (SSE). Telegram handles it by dynamically editing the message in batches, and the TUI handles it by updating textual widgets.
*   **Modules responsible:** agent.py (Orchestration loop), types.py (Data shapes).

### 2.3 Local Context & Database-Backed Memory
*   **What it does:** Ensures that all chats, system configurations, and interactions persist between reboots entirely locally.
*   **How it works:** Employs an `aiosqlite` single-file database mapped through `sqlalchemy` and alembic for migrations. The database groups messages into `Session` objects containing `Message` models with `role`, `content`, and `tool_calls`.
*   **Internal behavior:** It sidesteps common `asyncio.CancelledError` bugs by configuring the engine with `NullPool` (disabling pooled persistent connections for an ephemeral SQLite database) ensuring clean teardowns if a client disconnects.
*   **Modules responsible:** database.py, models.py, manager.py.

### 2.4 Cryptographic API Key Management & Sudo Safeties
*   **What it does:** Securely stores API keys for various LLM providers in the database and prevents malicious autonomous shell execution.
*   **How it works:** Keys are encrypted using `cryptography.fernet` symmetric encryption before database insertion, indexed by hashed values. 
*   **Sudo Mechanism:** For destructive tools (e.g., shell command execution), the agent halts and creates a `PendingConfirmation` loop. A limited-time "sudo authorized session" is maintained in memory. The user maps a UI action (button click or callback query) to resolve the confirmation.
*   **Modules responsible:** api_key_manager.py, api_key.py, agent.py (Validation loops).

### 2.5 Resilient Model Orchestration & Cooldowns
*   **What it does:** Prevents the bot from breaking entirely if an API key gets rate-limited by shifting to fallbacks or managing internal cooldowns dynamically.
*   **How it works:** DB tracks `model_cooldowns` (a JSON dictionary). If an API responds with `429 Rate Limit`, the wrapper flags the key, applies a timestamped "until" limit, and rotates to an alternative key matching the provider.
*   **Modules responsible:** gemini.py, base.py, models.py (`APIKey.model_cooldowns`).

---

# 3. Architecture Deep Dive

The architectural pattern is deeply inspired by Hexagonal Architecture (Ports and Adapters). The central business logic (`agent/`, `core/`, `domain models`) is entirely isolated from the transport layers (`interfaces/`).

### 3.1 High-Level Systems
1.  **Core Domain Layer:** `db/models.py` and `core/types.py` represent the fundamental truths of the system (Sessions, Messages, Tool Results).
2.  **Service Layer:** agent.py, `services/`, and `planner.py`. This orchestrates requests: formatting prompts, loading history, executing cryptographic routines.
3.  **Adapter Layer (Inputs):** `interfaces/web/`, `interfaces/telegram/`, `interfaces/tui/`. They only know how to receive inputs and translate them into a `chat(message=..., session_id=...)` method call.
4.  **Adapter Layer (Outputs):** `tools/`. They interface with the host filesystem, OS processes, or internet search APIs.

### 3.2 Component Communications & Request Lifecycle
*   **Phase 1: Input.** User types "What is in my root dir?". (e.g., in Web UI). Svelte sends this to FastAPI `/chat/stream`. 
*   **Phase 2: Context Aggregation.** The API route provisions an AsyncSession, initializes an invocation of `Agent.chat(...)`. The agent loops in `MemoryManager` to pull up previous messages. 
*   **Phase 3: The LLM Loop.** The `planner` merges `agent_capabilities.md` and tool schemas. The request hits Gemini. Gemini returns a `function_call` payload.
*   **Phase 4: Tool Execution.** The `tool_registry` identifies the function. (e.g., `list_directory.py`). Executed locally. 
*   **Phase 5: Resumption.** Result appended to state, LLM triggered again. LLM outputs final string.
*   **Phase 6: Streaming.** Each text chunk is yielded live back to the FastAPI endpoint, streamed via SSE to the browser, updating Svelte reactivity.

### 3.3 System Strengths and Resilience
*   **`NullPool` Async Handling:** Using standard connection pools with Asyncio in SQLite causes massive race conditions on interrupted streams. Explicitly bypassing this provides extremely resilient connection loops.
*   **Shielding Cancellations:** The stream pipeline handles `asyncio.CancelledError` (when a browser tab closes mid-generation) by delegating database closure into an independent, unshielded asyncio event task, leaving no orphan queries.
*   **Strict Security Posture:** Not relying on .env files for key persistence; allowing dynamically updatable keys that are encrypted at rest with Fernet.

---

# 4. Folder Structure Analysis

### Root & Build Constraints
*   **pyproject.toml / Makefile / uv.lock:** Project relies on standard `setuptools`, Python 3.13, and is managed conceptually by modern dependency systems (likely `uv`). The CLI entry point maps `vela` directly to `main:cli`.
*   **alembic:** Standard Alembic environments and templated migrations for tracking local DB schema drifts. Migrations exist for settings, adding API key tables, and model cooldowns.

### frontend
*   **Purpose:** Houses an actively decoupled Web SPA.
*   **Structure:** It is a Svelte 5 application bundled by Vite. Marked is used for Markdown parsing, and DOMPurify for security to prevent XSS payloads directly injecting HTML formatting from the LLM. 
*   **Roles:** `App.svelte` holds layout, nested structures for `components/` (Chat Input, Model Selector). It builds out to dist which is natively mounted as a static path by the Web adapter.

### src (Core Application)
*   `cli.py` & main.py: The Typer CLI configuration mapping commands like `tui`, `web`, `telegram`, `apikey` and `safety` overrides.
*   `agent/`: The brain. agent.py contains the stream/run implementations, maintaining strict runtime invariants (Sudo auth caches, React Loop orchestration).
*   `config/`: Exposes `settings.py` built on `pydantic-settings` tracking `WEB_HOST`, `DB_URL`, etc., and runtime configurations (logging parameters, workspace bindings).
*   `core/`: Core internal APIs. Interfaces for building a `Tool` class, custom schemas, and base definitions (Enums).
*   `data/`: Static bootstrap data (empty configs).
*   `db/`: Defines the raw SQLite engine configuration, session generators, repositories (data access layers for `APIKey` and `Settings`), and ORM definitions (Models).
*   `interfaces/`
    *   `api/`: FastAPI routers split by domain (`chat/`, `sessions/`, `settings/`, `api_keys/`) keeping the actual endpoints tiny.
    *   `cli/`: Legacy/alternative logic.
    *   `discord/`: Seeded directory for future adapter integration.
    *   `telegram/`: `bot.py` and `handlers.py`, containing logic deeply embedded in `python-telegram-bot` specifics like polling configurations, markdown parsing escaping, webhook lifecycles.
    *   `tui/`: Rich interactive interface utilizing the `Textual` library with nested layout widgets.
    *   `web/`: The `FastAPI` instance initializer itself and the mount paths for the dist compiled site.
*   `llm/`: Standardized abstraction (`base.py`) mapping disparate provider libraries (`google-genai`, `openai`) into a generalized system. Includes exception translation ensuring `RateLimitError` is consistent across providers.
*   `memory/`: Simple CRUD abstraction logic to aggregate messages into a standardized format for the LLM injection.
*   `planner/`: Handles the tricky job of system prompting. Injects workspace contexts, system constraints, instructions (`agent_capabilities.md`), and limits into a structured initial system prompt message.
*   `services/`: Business services combining internal repositories and utilities (e.g. `APIKeyManager` blending `APIKeyRepository` queries with `Fernet` logic). 
*   `tools/`: Granular modules (`shell_command.py`, `file_edit.py`, `grep.py`). Tools export single behaviors matching standard JSON schemas required by the LLM function calls.

---

# 5. Runtime Flow

### Initialization Sequence
1.  **Invoked:** User executes `vela start web telegram`.
2.  **Environment loading:** `initialize_runtime()` runs. Defines local `.vela` folder roots or workspace anchors.
3.  **Config & Logging:** Parses .env or configuration JSON files, sets up `rich` logging handlers.
4.  **Database Boot:** Alembic executes startup assertions (if configured). SQLAlchemy `create_async_engine` initialized.
5.  **Agent Prep:** Dependencies instantiated. `ToolRegistry` scans the `tools/` folder. `APIKeyManager` instantiated with the `Fernet` encryption pool. `Agent` is bound.
6.  **Task Gathering:** `asyncio.gather()` loops through desired interfaces. `start_web(agent)` initializes Uvicorn block; `start_telegram(agent)` initializes Python-Telegram-Bot polling blocks.

### Request Processing Flow
1.  Message arrives at an interface (e.g., TUI input).
2.  Route calls `agent.chat(message, channel="tui")`.
3.  Agent generates session if not provided, queries SQLite `sessions` and `messages`.
4.  History sent to LLM provider.
5.  Provider emits streaming chunks. Agent wraps them into `StreamEvent(type="text", content=chunk)`.
6.  If tool requested, Agent stops streaming chunks to GUI, executes `Tool.execute()`, feeds back the result to the LLM, and triggers generation resumption.
7.  End of conversation: `db.close()` occurs early, and trailing stream stops.
8.  *Assumption Label:* We assume tool-call UI components pause their chat streams slightly to inject a "tool executing" bubble based on the frontend structure containing `ThinkingIndicator` and `ToolBlock` elements.

### Shutdown Flow
When `SIGINT` (Ctrl+C) is caught, or when `vela` receives a `/shutdown` POST request from the web, the global application states toggle exit conditions. Uvicorn terminates server loops gracefully, PTB halts the updater loops. Event loops finalize active database sessions.

---

# 6. AI Assistant System

The AI System is inherently modular, utilizing an adapter-over-provider pattern.

*   **Prompt Flow:** The system prompt forces the assistant to act as a system-integrated helper locally, providing parameters on *how* to use the underlying terminal environments safely. The DB keeps a history of the current interaction via `MemoryManager`, loading an un-truncated history context (or token-measured truncation depending on implementation limits).
*   **Tool Calling Logic:** Implemented directly upon LLM capabilities. The prompt is paired with `tools` mappings automatically generated from Pydantic or basic reflection from `__init__.py` in the `tools/` module. The LLM dictates arguments. 
*   **The Sudo Authorization Loop:** Crucial security layer. When a destructive `shell_command.py` is called by the LLM:
    1.  The tool proxy asserts local `_is_sudo_authorized`.
    2.  If false, tool returns an artificial observation forcing the LLM to yield a `PendingConfirmation` token explicitly indicating a user confirmation is required.
    3.  User interface flashes a "Confirm / Reject" modal.
    4.  If confirmed, authorization token is granted to `session_id`. Tool executes. Re-runs React loop.
*   **Streaming Strategy:** Deep reliance on Python's Generator iterators. Each frame generated from `google-genai` creates localized event streams allowing instant-response feelings on TUI, Web, and chunked batches on Telegram (due to Telegram API rate limits on editing messages).

---

# 7. Interface Analysis

### 7.1 CLI (cli.py & main.py)
*   **Pattern:** Uses `typer` to easily manage subcommands.
*   **Responsibility:** Provides lifecycle commands, API key administration logic (`vela apikey ...`), and system-wide overrides without spinning up graphic interfaces. Uses `rich.console` for beautiful colored terminal outputs. Handles health-checks simulating `ps` lookup using `ctypes` mappings on Windows or standard `os.kill(0)` routing on Posix.

### 7.2 Web Interface (frontend & web)
*   **Frontend Interaction:** Modern Svelte 5 structure compiled alongside FastAPI's backend routes. `sessionService.svelte.js` handles client-side state reactivity via signals.
*   **Backend Interaction:** `FastAPI` routes heavily leverage `app.state` caching to attach the single `agent` singleton preventing initialization delays.
*   **Communication:** `yield` streams mapped to standard HTTP Streaming Responses (likely EventSource / SSE format) enabling live typing. Form requests fetch settings and keys interacting immediately with underlying SQLAlchemy endpoints.

### 7.3 TUI (tui)
*   **Framework:** Leveraging the `Textual` Python library. It overrides `on_mount` loops and defines custom widgets (`chat_view.py`, `command_palette.py`, `input_row.py`).
*   **Responsibility:** Delivering a terminal-embedded application utilizing CSS-like descriptors for highly reactive interfaces directly mirroring full-GUI capabilities without escaping a standard SSH or local terminal environment.

### 7.4 Telegram Integration (telegram)
*   **Framework:** `python-telegram-bot` (`PTB`).
*   **Mechanisms:** Booting with low-level explicit `updater.start_polling` avoiding main loop clashing native to higher-level wrappers. Supports polling AND Webhooks dynamically. 
*   **Routing:** Dedicated handler routing `CallbackQueryHandler` for catching inline keyboard button presses mapping to Sudo tool authorizations and API Key enablement toggles directly within message chats. Edits messages sequentially with backoff-pooling to simulate streaming responses.

---

# 8. Technical Stack Breakdown

| Technology Core | Purpose & Justification |
| :--- | :--- |
| **Python 3.13** | Main backend language enforcing modern semantic structures, strong typing patterns, and ultra-high-performance asyncio handlers necessary for asynchronous concurrent event streams. |
| **Svelte 5** | Frontend reactive framework chosen for extremely minimal bundle size and exceptional DX without virtual DOM overhead, fitting nicely via statically mounted API apps. |
| **FastAPI** | High-performance API serving web hooks and backend connections. Extremely fast integration with `pydantic` making schema-bindings strict. |
| **SQLAlchemy / Alembic** | Standard robust database modeling mapped to local SQLite databases. Ensures strictly typed mapping structures with migration handling capability on version upgrades. |
| **Aiosqlite** | Asynchronous layer bridging SQLite natively into AsyncIO tasks without thread-pool bottlenecks. |
| **Textual / Rich** | Premium library for terminal interfaces. |
| **Python-Telegram-Bot** | Extensively typed API wrapper. |
| **Cryptography (Fernet)** | Used explicitly out of strong security postures preventing plaintext exposure of sensitive third-party Gemini/OpenAI parameters directly within the local state layer. |

---

# 9. Tool/Function System Analysis

The application enforces autonomy securely by providing internal modules mapped as "Tools".

*   **Discovery and Registration:** `ToolRegistry` aggregates `Tool` subclasses. Classes implement structural `.name`, `.description`, `.parameters` natively mimicking JSON Schemas mapped directly to vendor LLM APIs (OpenAI function calling, Gemini tool specs).
*   **Execution Wrappers:** Interface dictates a standard `.execute(**kwargs)` payload outputting structured dict objects.
*   **Sandbox Safety:** Because tools represent filesystem overwriting (`file_edit.py`, `file_write.py`) and command executions (`shell_command.py`), execution logic includes isolated catch-blocks returning the traceback output to the model if it fails, allowing the model to debug its own failures.
*   *(Assumption Label):* The tools likely invoke `asyncio.subprocess` directly instead of blocking `os.system` routines in order not to block stream concurrency loops handling parallel API queries simultaneously mapping to Telegram and Web clients.

---

# 10. Final System Summary

**High-Level System Identity:**
Vela functions as an autonomous, multi-tenant proxy agent allowing power-users absolute localized control to instruct and evaluate complex logic utilizing large contexts natively tied to personal machinery. 

**Core Strengths:**
1.  **Architecture:** The Hexagonal design successfully separates the "Brain Pipeline" from the "View Pipeline". The integration points are purely string queries and async stream hooks, meaning a Discord plugin or Slack integration can be cleanly added by mapping three interface hooks and writing zero logic.
2.  **Concurrency Mastery:** Explicit protection against memory leakage from database pools by manually handling the ASGI cancellation scopes guarantees minimal footprints during sustained complex generations. 
3.  **Local Security Posture:** Abstracting settings and keys into Fernet-encrypted SQlite tables guarantees simple binary portability `.vela/db.sqlite` without risking environment variable injections. Built-in `Sudo` loops securely lock down rogue LLM hallucinations in terminal instances.

Vela is a sophisticated, highly modular system perfectly oriented around taking advantage of contemporary agentic AI logic mapped seamlessly against user workflows ranging across desktop, terminal, and mobile spaces simultaneously accessible through the web and portable to external to that proxy mapping directly down to standard mobile channels via Telegram bot interfaces.