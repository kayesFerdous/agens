# Agens

Agens is a local assistant with CLI, TUI, web, and Telegram interfaces.

## Install

The recommended desktop install is `pipx`, which keeps Agens isolated from your project Python environments:

```bash
pipx install agens
agens --version
agens web
```

Standard Python installation remains supported:

```bash
pip install agens
```

Cross-platform installers are available in `scripts/`:

```bash
./scripts/install.sh install
./scripts/install.sh upgrade
./scripts/install.sh uninstall
```

On Windows PowerShell:

```powershell
.\scripts\install.ps1 install
.\scripts\install.ps1 upgrade
.\scripts\install.ps1 uninstall
```

See [docs/installation.md](docs/installation.md) for Linux, macOS, Windows, Docker, CI, troubleshooting, and developer setup.

## Run

```bash
agens web
agens tui
agens chat "Hello"
agens apikey add personal gemini <your-api-key>
```

The first run creates per-user runtime configuration and secrets in the OS-specific user config directory. Environment variables can override runtime settings, and `AGENS_ENV_FILE=/path/to/env` can opt into an additional dotenv file.

## Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>. Runtime data is stored in named Docker volumes for config, database, memories, and workspace data.

## Development

```bash
uv sync
make build-frontend
uv run agens --version
uv run agens web
```

Build release artifacts with:

```bash
make build
```
