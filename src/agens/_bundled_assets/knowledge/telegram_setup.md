# Telegram Setup

Interact with your agent via Telegram using the built-in adapter.

## 1. Setup & Config
First, get a bot API token from Telegram:
1. Open up the Telegram app and search for **@BotFather** (look for the verified blue checkmark).
2. Start a chat and send the command `/newbot`.
3. Follow the on-screen instructions to give your bot a display name and a unique username.
4. BotFather will generate an HTTP API Token (e.g., `123456789:ABCdefGHIjklmNOPQRsTUVwxyz123456`). Copy this token.

Next, provide the token to Agens:
- **Via Chat:** Ask the agent directly: *"Set my Telegram token to <token>"*.
- **Via CLI:** Run `agens telegram set-token <token>`

## 2. Start Bot
- **Telegram only:** `agens telegram`
- **Telegram + Web:** `agens start web telegram`
*(Uses long-polling by default. Set `WEBHOOK_HOST` env var for webhooks).*

## 3. Security
**Sudo Blocked:** All sudo/confirmation-required commands are rigidly blocked on Telegram for security. Use the TUI for sensitive actions.
