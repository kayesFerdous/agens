# interfaces/telegram/bot.py
from cryptography.fernet import Fernet
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config.logging import setup_logging
from config.settings import settings
from .handlers import start, help_me, handle_message

import asyncio

setup_logging()


async def _on_startup(app: Application) -> None:  # type: ignore[type-arg]
    """Runs once after the bot is initialised but before polling starts."""
    app.bot_data["agent"] = None
    app.bot_data["agent_lock"] = asyncio.Lock()
    app.bot_data["fernet"] = Fernet(settings.FERNET_SECRET.encode())


def run() -> None:
    app = (
        Application.builder()
        .token(settings.TELEGRAM_TOKEN)
        .post_init(_on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_me))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running…")
    app.run_polling()


if __name__ == "__main__":
    run()
