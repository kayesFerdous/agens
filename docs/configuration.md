# Configuration & Key Management

Agens segregates its operating settings, memory storage, and secure credentials across three distinct operational boundaries:

1. **Environment Variables**: Low-level engine parameters defined in `settings.py` or `.env`.
2. **User Memories**: Highly dynamic facts stored in `config.json` and deep-merged via agent prompts.
3. **SQLite Database Schema**: Persistent session histories, encrypted keys, calendar events, and settings.

---

## 1. Environment Configuration

Low-level settings are parsed by Pydantic-Settings from environment variables or an `agens.env` file specified by the user:

| Variable | Purpose | Default Value |
| :--- | :--- | :--- |
| `PRODUCTION` | Disables debug logs and optimizes execution verbosity | `True` |
| `DATABASE_URL` | SQLAlchemy-compatible SQLite connection string | `sqlite+aiosqlite:///.agens/db.sqlite` |
| `FERNET_SECRET` | Base64-encoded key used to encrypt provider API keys | Auto-generated on first startup |
| `SESSION_SECRET_KEY` | Hex or random key used to secure active Web UI cookies | Auto-generated on first startup |
| `WORKSPACE_ROOT` | Scopes directory tools to prevent filesystem escape | Current working directory (CWD) |
| `AGENS_ENV_FILE` | Path to an external env configuration file | CWD or `.agens/` |
| `WEB_HOST` | Host address uvicorn binds to | `0.0.0.0` |
| `WEB_PORT` | Port number uvicorn listens on | `8000` |

> [!TIP]
> **Customizing Web Bind Port**: While the web server defaults to port `8000`, you can dynamically override it via environment variables or CLI options when booting the client:
> - Direct CLI parameter: `agens web --port 8080` (or `-p 8080`)
> - Direct environment override: `WEB_PORT=8080 agens web`

---

## 2. Cryptographic API Key Management

Agens treats third-party API credentials (Gemini, OpenAI, DeepSeek, etc.) with strict security. Plaintext API keys are **never** stored on disk or written to plaintext config files.

### Encryption at Rest
At first launch, the engine generates a cryptographic `FERNET_SECRET` key and writes it securely to local configuration.
1. When you add an API key, it is encrypted using `cryptography.fernet` symmetric encryption.
2. The encrypted payload, along with an in-memory hash index, is saved to the SQLite database.
3. Decryption happens **exclusively in-memory** during an active LLM generation request.

### API Key Administration
API keys are easily managed using standard CLI commands:

```bash
agens apikey add    <label> <provider> <api_key>   # Register and encrypt a new key
agens apikey list                                   # Show all registered keys (hints only)
agens apikey remove <label>                         # Permanently delete a key
agens apikey disable <label>                        # Temporarily disable a key from rotation
agens apikey enable  <label>                        # Re-enable a disabled key
```

---

## 3. Resilient Key Rotation & Cooldowns

To ensure maximum availability, Agens incorporates transparent model and key failovers. If you have registered multiple API keys or are utilizing model fallback options:

1. **Error Interception**: When a provider adapter intercepts a `429 Rate Limit` or quota exhausted error from an API call, it raises an internal `RateLimitError`.
2. **Cooldown Tracking**: The `APIKeyManager` catches this exception and records a timestamped cooldown directly inside the DB `api_keys.model_cooldowns` JSON column:
   - *Rate limits*: Placed on cooldown for `60` seconds by default.
   - *Quota exhaustion*: Placed on cooldown for `24` hours.
3. **Transparent Fallback**: The LLM router automatically bypasses the cooled-down key, queries the database for the next eligible API key for the requested provider, and retries the generation request without interrupting the user's active session.

---

## 4. Persistent User Memories

Rather than relying on short-term token window contexts, Agens utilizes a long-term dynamic configuration system (`config.json`) to persist user facts:

### Memory Storage Flow
The agent can decide to remember facts about you (e.g. location, coding languages, career goals) by executing the `update_config` tool. This writes directly into the `user.memories` key inside `config.json`:

```json
{
  "user": {
    "memories": {
      "city": "Berlin",
      "specialty": "FastAPI and Svelte",
      "style": "clean, concise, self-contained code"
    }
  }
}
```

### Dynamic Injection
On every single chat interaction, the `prompt_builder.py` module loads these memory keys and dynamically injects them into the LLM's active system prompt, preserving continuity.

### Forgetting Memories
When a user instructs the assistant to "forget" a fact, the agent calls `update_config` with a target key set to `null`. The engine's deep-merge algorithm automatically prunes that key and deletes it from the `config.json` file.

---

## 5. SQLite Database Schema

Agens stores structural operational states in a local single-file SQLite database. Schema transitions are managed dynamically using Alembic migrations:

| Table | Contents |
| :--- | :--- |
| `sessions` | Active conversation thread IDs, summaries, and creation timestamps. |
| `messages` | Chat history records including prompt content, role tags, and tool schemas/results. |
| `api_keys` | Encrypted Fernet strings, provider labels, active/disabled state, and cooldowns. |
| `schedule_events` | Calendar entries, reminders, and user-scheduled alert data. |
| `settings` | Row-level configuration parameters (e.g. global `safety_mode` state). |

Schema upgrades are applied automatically during engine bootstrap, removing the need for manual database updates.

---

## Navigation

- 🏠 **[Home (README)](../README.md)**
- 🚀 **[Installation & Setup](installation.md)**
- 🏗️ **[Architecture Deep Dive](architecture.md)**
- 🛠️ **[Tool System & Custom Tools](tools.md)**
- 💻 **[Developer & Contributor Manual](development.md)**
