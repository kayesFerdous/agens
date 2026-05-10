# interfaces/telegram/bot.py — Telegram adapter: start_telegram(agent) entry point
from __future__ import annotations

import logging
import asyncio

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from agent.agent import Agent
from config.logging import setup_logging
from config.settings import settings
from config.config_manager import ConfigManager
from . import handlers

setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def start_telegram(agent: Agent) -> None:
    """Build and run the Telegram bot, sharing the provided agent instance.

    Uses PTB's low-level async API (initialize → start → updater.start_polling)
    instead of run_polling(), which internally calls loop.run_until_complete()
    and therefore cannot be used inside an already-running asyncio event loop.
    """

    config_mgr = ConfigManager(settings.CONFIG_PATH)
    config = config_mgr.load_config()

    if not config.telegram_token:
        logger.error("No Telegram token configured in config.json. Bot will not start.")
        return

    app = (
        Application.builder()
        .token(config.telegram_token)
        .post_init(handlers.on_startup)
        .build()
    )

    # Attach the agent eagerly — no lazy init, no lock needed.
    app.bot_data["agent"] = agent

    app.add_handler(CommandHandler("start", handlers.start_command))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("model", handlers.model_command))
    app.add_handler(CommandHandler("models", handlers.model_command))
    app.add_handler(CommandHandler("keys", handlers.get_keys_command))
    app.add_handler(CallbackQueryHandler(handlers.handle_model_callback, pattern=r"^model:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    # `async with app` calls initialize() on enter and shutdown() on exit.
    async with app:
        await app.start()

        if settings.WEBHOOK_HOST:
            webhook_url = f"https://{settings.WEBHOOK_HOST}/{config.telegram_token}"
            logger.info("Starting Telegram bot with webhook: %s", webhook_url)
            await app.updater.start_webhook(  # type: ignore[union-attr]
                listen="0.0.0.0",
                port=settings.WEBHOOK_PORT,
                webhook_url=webhook_url,
            )
        else:
            logger.info("Starting Telegram bot with long-polling")
            await app.updater.start_polling()  # type: ignore[union-attr]

        try:
            # Block here until cancelled (KeyboardInterrupt → CancelledError
            # from asyncio.gather in main.py).
            await asyncio.Event().wait()
        finally:
            # Graceful shutdown — mirrors what run_polling() does internally.
            await app.updater.stop()  # type: ignore[union-attr]
            await app.stop()
