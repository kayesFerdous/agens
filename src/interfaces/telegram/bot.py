# interfaces/telegram/bot.py — Telegram adapter: start_telegram(agent) entry point
from __future__ import annotations

import logging
import asyncio

from telegram.error import NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from agent.agent import Agent
from config.logging import setup_logging
from config.settings import settings
from config.config_manager import ConfigManager
from . import handlers

setup_logging()
logger = logging.getLogger(__name__)
BOT_CONNECT_TIMEOUT = 15.0
BOT_READ_TIMEOUT = 20.0
BOT_WRITE_TIMEOUT = 20.0
BOT_POOL_TIMEOUT = 5.0
POLLING_TIMEOUT = 30
POLLING_READ_TIMEOUT = 40.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def start_telegram(agent: Agent) -> None:
    """Build and run the Telegram bot, sharing the provided agent instance.

    Uses PTB's low-level async API (initialize → start → updater.start_polling)
    instead of run_polling(), which internally calls loop.run_until_complete()
    and therefore cannot be used inside an already-running asyncio event loop.
    """

    config_mgr = ConfigManager()
    config = config_mgr.load_config()

    if not config.telegram_token:
        logger.error("No Telegram token configured in config.json. Bot will not start.")
        return

    bot_request = HTTPXRequest(
        connect_timeout=BOT_CONNECT_TIMEOUT,
        read_timeout=BOT_READ_TIMEOUT,
        write_timeout=BOT_WRITE_TIMEOUT,
        pool_timeout=BOT_POOL_TIMEOUT,
    )
    polling_request = HTTPXRequest(
        connect_timeout=BOT_CONNECT_TIMEOUT,
        read_timeout=POLLING_READ_TIMEOUT,
        write_timeout=BOT_WRITE_TIMEOUT,
        pool_timeout=BOT_POOL_TIMEOUT,
    )

    app = (
        Application.builder()
        .token(config.telegram_token)
        .request(bot_request)
        .get_updates_request(polling_request)
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
    app.add_handler(CallbackQueryHandler(handlers.handle_key_toggle_callback, pattern=r"^keytoggle:"))
    app.add_handler(CallbackQueryHandler(
        handlers.handle_key_bulk_callback, pattern=f"^{handlers.KEY_BULK_CALLBACK_PREFIX}"
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    app.add_error_handler(handlers.error_handler)

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
            await app.updater.start_polling(  # type: ignore[union-attr]
                timeout=POLLING_TIMEOUT,
                error_callback=_log_polling_error,
            )

        try:
            # Block here until cancelled (KeyboardInterrupt → CancelledError
            # from asyncio.gather in main.py).
            await asyncio.Event().wait()
        finally:
            # Graceful shutdown — mirrors what run_polling() does internally.
            await app.updater.stop()  # type: ignore[union-attr]
            await app.stop()


def _log_polling_error(error: TelegramError) -> None:
    if isinstance(error, RetryAfter):
        logger.warning("Telegram polling rate-limited; retry_after=%s", error.retry_after)
        return
    if isinstance(error, (TimedOut, NetworkError)):
        logger.warning("Telegram polling network issue: %s", error)
        return
    logger.exception("Telegram polling error", exc_info=(type(error), error, error.__traceback__))
