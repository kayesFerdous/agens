# Installation & Setup

[Home (README)](../README.md) · [Architecture Deep Dive](architecture.md) · [Tool System](tools.md) · [Configuration](configuration.md) · [Developer Manual](development.md)

Agens supports `pipx`, `pip`, platform installer scripts, and Docker. `pipx` is preferred for local machines because it gives Agens an isolated Python environment and keeps project virtual environments untouched.

## Requirements

- Python 3.13 or newer for native installs.
- `pip` for the fallback installer path.
- `pipx` recommended.
- Docker and Docker Compose for container usage.

## Linux

Recommended:

```bash
pipx install agens
agens --version
agens web
```

One-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash
```

Alternative (local script):

```bash
chmod +x scripts/install.sh
./scripts/install.sh install
```

Pinned install:

```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash -s -- --version 0.1.0
```

CI/non-interactive:

```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash -s -- --non-interactive --method pipx
```

## macOS

Recommended:

```bash
brew install pipx
pipx ensurepath
pipx install agens
agens web
```

One-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash
```

Alternative (local script):

```bash
chmod +x scripts/install.sh
./scripts/install.sh install
```

If the `agens` command is not found after installation, restart your shell or run `pipx ensurepath`.

## Windows

One-line installer (PowerShell):

```powershell
irm https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.ps1 | iex
```

Alternative (local script):

```powershell
.\scripts\install.ps1 install
agens --version
agens web
```

Pinned install:

```powershell
.\scripts\install.ps1 install -Version 0.1.0
```

CI/non-interactive:

```powershell
.\scripts\install.ps1 install -NonInteractive -Method pipx
```

Manual install:

```powershell
py -3.13 -m pip install --user pipx
py -3.13 -m pipx ensurepath
pipx install agens
```

## Upgrade

With `pipx`:

```bash
pipx upgrade agens
```

With `pip`:

```bash
python -m pip install --upgrade agens
```

With the installers:

```bash
./scripts/install.sh upgrade
```

```powershell
.\scripts\install.ps1 upgrade
```

## Uninstall

With `pipx`:

```bash
pipx uninstall agens
```

With `pip`:

```bash
python -m pip uninstall agens
```

With the installers:

```bash
./scripts/install.sh uninstall
```

```powershell
.\scripts\install.ps1 uninstall
```

Uninstalling the package does not delete your runtime data. Agens stores config, generated secrets, preferences, and the default SQLite database in the OS user config directory. Remove that directory manually only when you intentionally want to delete local data.

## Docker

Build and run production:

```bash
docker compose up --build
```

Open <http://localhost:8000>.

Useful commands:

```bash
docker compose logs -f agens
docker compose exec agens agens --version
docker compose down
```

Persistent Docker volumes:

- `agens_config`: generated secrets, config, preferences, knowledge, prompts, logs.
- `agens_database`: SQLite database, sessions, encrypted API key records.
- `agens_memories`: reserved persistent memory volume.
- `agens_runtime`: reserved runtime data volume.
- `agens_workspace`: default workspace exposed to file tools.

The production image runs as a non-root user and exposes only port `8000`. It uses a health check against `/health`.

Developer Docker profile:

```bash
docker compose --profile dev up --build agens-dev
```

The dev profile serves the API on port `8000` and the Vite frontend on port `5173`.

## Configuration

Common environment variables:

```text
WEB_HOST=0.0.0.0
WEB_PORT=8000
DATABASE_URL=sqlite+aiosqlite:////data/db/agens.db
WORKSPACE_ROOT=/workspace
DEFAULT_PROVIDER=gemini
DEFAULT_MODEL=gemini-2.5-flash-lite
AGENS_ENV_FILE=/path/to/agens.env
```

Agens generates `SESSION_SECRET_KEY` and `FERNET_SECRET` on first run. Operators can provide them through environment variables or an `AGENS_ENV_FILE` when they need stable externally managed secrets.

## Developer Setup

```bash
uv sync
make build-frontend
uv run agens --version
uv run agens web
```

Build release artifacts:

```bash
make build
```

The frontend build writes packaged web assets to `src/interfaces/web/dist`. Build the frontend before creating wheels or source distributions.

## Troubleshooting

`agens` command not found:

Run `pipx ensurepath`, restart your shell, or add your Python user scripts directory to `PATH`.

Python version error:

Install Python 3.13 or newer and rerun the installer with `--python /path/to/python` or `-Python C:\Path\To\python.exe`.

`pipx` not found:

Install `pipx`, or let the installer fall back to `pip --user`. The fallback avoids modifying active project virtual environments unless you intentionally run it inside one.

Docker container unhealthy:

Check logs with `docker compose logs agens`. Confirm port `8000` is free, volumes are writable, and required environment variables are valid.

Docker BuildKit / buildx errors:

If you see warnings or errors regarding BuildKit or the `buildx` plugin, we have configured the Dockerfiles to build cleanly with the legacy builder by default. However, you can enable BuildKit to benefit from faster build performance and caching:

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

On Linux systems, if `buildx` is missing, you can install it using your package manager (e.g., `apt-get install docker-buildx` or similar).

No API keys configured:

Add a key with:

```bash
agens apikey add personal gemini <your-api-key>
```

```bash
docker compose exec agens agens apikey add personal gemini <your-api-key>
```

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- 🛠️ **[Tool System & Custom Tools](tools.md)**
- ⚙️ **[Configuration & Key Management](configuration.md)**
- 💻 **[Developer & Contributor Manual](development.md)**

