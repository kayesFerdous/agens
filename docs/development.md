# Developer & Contributor Manual

[Home (README)](../README.md) · [Architecture Deep Dive](architecture.md) · [Installation & Setup](installation.md) · [Tool System](tools.md) · [Configuration](configuration.md)

---

Welcome! This guide is written for anyone looking to hack on the Agens codebase, compile release assets, add new interface channels, or contribute code.

---

## 1. Local Workspace Setup

Setting up Agens on your machine for development takes only a few minutes. We use the ultra-fast tool **`uv`** to manage Python versions and environments.

### Step 1: Get the Code & Dependencies
Make sure Python 3.13+ is installed, clone this repository, and run the following command to sync your environment:
```bash
uv sync
```

### Step 2: Compile the Web Dashboard
The modern Web UI is built with **Svelte 5** and **Vite**. Its files are packaged directly into our Python package so they can be served as static files by FastAPI.
To install node packages and build the UI assets, run:
```bash
make build-frontend
```
This writes the final compiled web app directly to `src/interfaces/web/dist`.

### Step 3: Verify the Setup
Run this quick command to make sure Python can find everything:
```bash
uv run agens --version
```

### Step 4: Run Developer Interfaces
You can launch any of our interfaces in developer mode:
```bash
uv run agens tui                  # Launches Textual TUI
uv run agens web                  # Launches Web Dashboard (FastAPI server + Svelte)
uv run agens telegram             # Boots Telegram listener (in polling mode)
```

---

## 2. Building Release Packages

If you want to package Agens into a standard Python distribution wheel (e.g., to upload to PyPI), run:
```bash
make build
```
This gathers your code, database migrations, and compiled frontend assets and bundles them into the `dist/` directory.

---

## 3. Adding a New Platform Interface (Slack, Discord, etc.)

Because Agens separates platform interfaces from the core brain, adding a new communication channel is incredibly easy. You do not need to modify any core AI logic.

To connect a new platform, implement three simple connection points:

### Step 1: Add a Boot CLI Command
Open `src/agens/main.py` and register a new subcommand to trigger your platform listener:
```python
# src/agens/main.py
@app.command()
def slack(ctx: typer.Context):
    """Launch the Slack adapter."""
    asyncio.run(start_slack_adapter(ctx.obj["agent"]))
```

### Step 2: Feed User Inputs to the Brain
In your platform runner, capture user text inputs and feed them to the central brain's `agent.chat()` method:
```python
# src/interfaces/slack/runner.py
async for event in agent.chat(
    message=user_input_text,
    session_id=active_db_session_id,
    channel=Channel.SLACK
):
    await handle_slack_stream_event(event)
```

### Step 3: Stream the Output Back to Your App
Agens streams events back to you as it thinks. Map these event types to your platform API:

| Event Type (`event.type`) | What it means | Recommended Action |
| :--- | :--- | :--- |
| `token` | AI generated a word chunk | Append the chunk to your active chat bubble. |
| `tool_call` | AI is running a tool | Show a visual loading spinner (e.g. "searching..."). |
| `status` | High-level status updates | Display a minor informational notification. |
| `error` | An exception was raised | Format the error cleanly and notify the user. |
| `done` | Generation completed | Finalize the chat bubble and save session state. |

---

## 4. Contributing Rules & Database Changes

We welcome your contributions! To keep the repository clean, please follow these rules:

*   **Python Standards**: Write clean, modern Python 3.13. Do not include legacy Python code.
*   **Keep Comments Intact**: Do not delete existing code comments or docstrings that are unrelated to your changes.
*   **Database Changes**: If you modify database tables:
    1. Create an Alembic migration script by running:
       ```bash
       alembic revision --autogenerate -m "describe your changes"
       ```
    2. Place the new file in your PR.
    3. Make sure the migration applies cleanly by running:
       ```bash
       alembic upgrade head
       ```

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🚀 **[Installation & Setup](installation.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- 🛠️ **[Tool System & Custom Tools](tools.md)**
- ⚙️ **[Configuration & Key Management](configuration.md)**
