from __future__ import annotations

from db.repositories.api_key import APIKeyRepository

SETUP_COMMAND = "vela apikey add <label> <provider> <key>"

NO_API_KEYS_SETUP_MESSAGE = (
    "No API keys found.\n\n"
    "Vela needs at least one API key before chat can start. Add one from your terminal:\n\n"
    f"  {SETUP_COMMAND}\n\n"
    "Example:\n"
    "  vela apikey add personal gemini YOUR_API_KEY"
)

NO_API_KEYS_TELEGRAM_MESSAGE = (
    "The assistant is not configured yet.\n\n"
    "Ask the admin to add an API key on the host machine:\n\n"
    f"{SETUP_COMMAND}"
)

NO_API_KEYS_CLI_MESSAGE = (
    "No API keys found.\n\n"
    "Add one before starting chat:\n\n"
    f"  {SETUP_COMMAND}\n\n"
    "Example:\n"
    "  vela apikey add personal gemini YOUR_API_KEY"
)

ALL_KEYS_UNAVAILABLE_MESSAGE = (
    "All API keys are currently exhausted or unavailable. "
    "You can switch models or add a new key with `vela apikey add <label> <provider> <key>`."
)


async def has_any_api_keys(repo: APIKeyRepository) -> bool:
    keys = await repo.list_keys(limit=1)
    return bool(keys)


def is_key_unavailable_error(message: str | None) -> bool:
    if not message:
        return False
    normalized = message.lower()
    markers = (
        "no active api keys",
        "no active keys",
        "all active keys",
        "all api keys",
        "all are on cooldown",
        "on cooldown for model",
        "gemini client is not initialized",
    )
    return any(marker in normalized for marker in markers)


def user_key_unavailable_message(message: str | None = None) -> str:
    return ALL_KEYS_UNAVAILABLE_MESSAGE if is_key_unavailable_error(message) else str(message or "Unknown error")
