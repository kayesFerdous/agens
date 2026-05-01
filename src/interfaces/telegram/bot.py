# interfaces/telegram/bot.py — Telegram adapter: start_telegram(agent) entry point
from __future__ import annotations

import logging
import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from agent.agent import Agent
from config.logging import setup_logging
from config.settings import settings
from db.database import async_session
from db import repository as session_repo

setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Startup hook — runs once, before polling/webhook begins
# ---------------------------------------------------------------------------

async def _on_startup(app: Application) -> None:  # type: ignore[type-arg]
    """Store the shared agent in bot_data so every handler can reach it."""
    # Agent is injected via app.bot_data["agent"] before run() is called.
    # This hook is a good place for any one-time async setup if needed later.
    logger.info("Telegram bot ready (agent already attached)")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def _start(update: Update, ctx) -> None:  # type: ignore[type-arg]
    await update.message.reply_text(  # type: ignore[union-attr]
        "Hello! I'm your assistant. Send me anything and I'll help you out."
    )


async def _help(update: Update, ctx) -> None:  # type: ignore[type-arg]
    await update.message.reply_text(  # type: ignore[union-attr]
        "Just send me a message and I'll do my best to help!"
    )


# ---------------------------------------------------------------------------
# Message handler — thin adapter: receive → agent.chat() → reply
# ---------------------------------------------------------------------------

async def _handle_message(update: Update, ctx) -> None:  # type: ignore[type-arg]
    if not update.message or not update.message.text:
        return

    user_text: str = update.message.text
    user_id: int = update.effective_user.id  # type: ignore[union-attr]
    agent: Agent = ctx.bot_data["agent"]

    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,  # type: ignore[union-attr]
        action="typing",
    )

    try:
        # Retrieve or create a persistent DB session for this Telegram user.
        if "session_id" not in ctx.user_data:
            async with async_session() as db:
                session = await session_repo.insert_session(
                    db, title=f"Telegram user {user_id}"
                )
            ctx.user_data["session_id"] = session.id
            logger.info("Created DB session %s for Telegram user %d", session.id, user_id)

        session_id: str = ctx.user_data["session_id"]

        # Collect the full answer from the streaming ReAct loop.
        answer_parts: list[str] = []
        async for event in agent.chat(user_text, session_id):
            if event.type == "token" and event.content:
                answer_parts.append(event.content)
            elif event.type == "error" and event.error:
                logger.error("Agent error: %s", event.error)
                await update.message.reply_text(  # type: ignore[union-attr]
                    f"⚠️ Something went wrong: {event.error}"
                )
                return

        reply = "".join(answer_parts).strip() or "I'm not sure how to answer that."
        await update.message.reply_markdown(reply)  # type: ignore[union-attr]

    except RuntimeError as e:
        logger.warning("Agent unavailable: %s", e)
        await update.message.reply_text(  # type: ignore[union-attr]
            "⚠️ The assistant is not configured yet. Please add an API key first."
        )
    except Exception as e:
        logger.exception("Unhandled error in _handle_message: %s", e)
        await update.message.reply_text(  # type: ignore[union-attr]
            "⚠️ An unexpected error occurred. Please try again."
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def start_telegram(agent: Agent) -> None:
    """Build and run the Telegram bot, sharing the provided agent instance.

    Uses PTB's low-level async API (initialize → start → updater.start_polling)
    instead of run_polling(), which internally calls loop.run_until_complete()
    and therefore cannot be used inside an already-running asyncio event loop.
    """
    app = (
        Application.builder()
        .token(settings.TELEGRAM_TOKEN)
        .post_init(_on_startup)
        .build()
    )

    # Attach the agent eagerly — no lazy init, no lock needed.
    app.bot_data["agent"] = agent

    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("help", _help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

    # `async with app` calls initialize() on enter and shutdown() on exit.
    async with app:
        await app.start()

        if settings.WEBHOOK_HOST:
            webhook_url = f"https://{settings.WEBHOOK_HOST}/{settings.TELEGRAM_TOKEN}"
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
