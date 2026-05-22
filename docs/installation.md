# Installation & Setup

[Home (README)](../README.md) · [Architecture Deep Dive](architecture.md) · [Tool System](tools.md) · [Configuration](configuration.md) · [Developer Manual](development.md)

---

Getting Agens running on your machine is designed to be quick and painless. You can install it using a package manager, simple installer scripts, or Docker.

## Requirements

Agens is built to be extremely lightweight. All you need is:
- **Python 3.13** or newer (for native setups)
- **`pipx`** (highly recommended, as it isolates Agens from your other Python projects)
- **Docker** & **Docker Compose** (if you prefer running inside containers)

---

## 🐧 Linux Setup

For most Linux distributions, you can install Agens in one command.

### Recommended (Using `pipx`)
```bash
pipx install agens
agens --version
agens web
```

### Direct One-Line Installer
```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash
```

> [!TIP]
> **Why we recommend `pipx`**: Running traditional `pip install` can mess up your system-wide Python packages or clash with virtual environments. `pipx` solves this by packaging Agens inside its own isolated folder, while still letting you run `agens` globally in your terminal.

---

## 🍏 macOS Setup

Installing on macOS is simple and works with Homebrew.

### Recommended (Using `pipx`)
```bash
brew install pipx
pipx ensurepath
pipx install agens
agens web
```

### Direct One-Line Installer
```bash
curl -fsSL https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.sh | bash
```

> [!NOTE]
> If your terminal says `command not found: agens` after installation, restart your terminal or run `pipx ensurepath` to refresh your terminal paths.

---

## 🪟 Windows Setup

Windows operators can get started natively via PowerShell or inside WSL2 (strongly recommended).

### Recommended (PowerShell One-Liner)
Run this command inside PowerShell:
```powershell
irm https://raw.githubusercontent.com/kayesFerdous/agens/main/scripts/install.ps1 | iex
```

### Manual Install
If you prefer doing it step-by-step:
```powershell
py -3.13 -m pip install --user pipx
py -3.13 -m pipx ensurepath
pipx install agens
agens web
```

> [!WARNING]
> **Run in WSL2 for the best experience**: While native Windows works well, running Agens inside **WSL2** (Windows Subsystem for Linux) is highly recommended. It is faster, handles shell tools natively, and has been road-tested much more extensively.

---

## 🐳 Docker Setup

If you prefer to run Agens inside a Docker container:

### Build and Launch
```bash
docker compose up --build
```
Once it builds, open [http://localhost:8000](http://localhost:8000) in your web browser.

### Troubleshooting and Monitoring
```bash
docker compose logs -f agens                  # View real-time logs
docker compose exec agens agens --version      # Run commands inside the container
docker compose down                           # Stop the container
```

### Where is my data stored?
Agens uses persistent Docker volumes so you never lose your keys or histories:
- `agens_config`: Saves your memories, preferences, and custom prompts.
- `agens_database`: Stores your local SQLite database (chat history and encrypted keys).
- `agens_workspace`: The specific folder that Agens is allowed to read and write files in.

---

## 🔄 Keeping Agens Updated

Whenever a new version of Agens is released, updating is simple:

### Using `pipx` (Recommended)
```bash
pipx upgrade agens
```

### Using Installer Scripts
```bash
# On Linux/macOS
./scripts/install.sh upgrade

# On Windows
.\scripts\install.ps1 upgrade
```

---

## ❌ Uninstalling

If you ever need to remove Agens:

### Using `pipx`
```bash
pipx uninstall agens
```

### Using Installer Scripts
```bash
# On Linux/macOS
./scripts/install.sh uninstall

# On Windows
.\scripts\install.ps1 uninstall
```

> [!IMPORTANT]
> **Your data remains safe**: Uninstalling the package will **never** delete your API keys, preferences, or chat histories. If you want to wipe everything permanently, you must manually delete the `.agens` directory located in your operating system's user config folder.

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- 🛠️ **[Tool System & Custom Tools](tools.md)**
- ⚙️ **[Configuration & Key Management](configuration.md)**
- 💻 **[Developer & Contributor Manual](development.md)**
