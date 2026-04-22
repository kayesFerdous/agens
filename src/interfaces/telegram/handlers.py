# interfaces/telegram/handlers.py
from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from agent.agent import Agent
from agent.factory import build_agent
from db.database import async_session
from db.repository import insert_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy agent initialisation
# ---------------------------------------------------------------------------

async def _get_or_create_agent(bot_data: dict) -> Agent:
    """Return the global Agent, building it on the first call (thread-safe)."""
    # Fast-path: agent already exists
    if bot_data["agent"] is not None:
        return bot_data["agent"]

    async with bot_data["agent_lock"]:
        # Double-check after acquiring the lock
        if bot_data["agent"] is not None:
            return bot_data["agent"]

        logger.info("First message received — building agent…")
        fernet = bot_data["fernet"]
        async with async_session() as db:
            agent = await build_agent(db, fernet)

        bot_data["agent"] = agent
        logger.info("Agent built and cached globally.")
        return agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_session_id(user_id: int, user_data: dict) -> str:
    """Return a persistent DB session ID for this Telegram user."""
    if "session_id" in user_data:
        return user_data["session_id"]

    async with async_session() as db:
        session = await insert_session(db, title=f"Telegram user {user_id}")
        user_data["session_id"] = session.id
        logger.info("Created DB session %s for Telegram user %d", session.id, user_id)
        return session.id


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(  # type: ignore[union-attr]
        "Hello! I'm your assistant. Send me anything and I'll help you out."
    )


async def help_me(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(  # type: ignore[union-attr]
        "Just send me a message and I'll do my best to help!"
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_text: str = update.message.text  # type: ignore[union-attr]
    user_id: int = update.effective_user.id  # type: ignore[union-attr]

    # Show a typing indicator while we think
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,  # type: ignore[union-attr]
        action="typing",
    )

    try:
        agent = await _get_or_create_agent(ctx.bot_data)
        session_id = await _get_or_create_session_id(user_id, ctx.user_data)  # type: ignore[arg-type]
        fernet = ctx.bot_data["fernet"]

        # Collect the full answer from the streaming ReAct loop
        answer_parts: list[str] = []
        async with async_session() as db:
            async for event in agent.run_stream(user_text, session_id, db, fernet=fernet):
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
        # Typically "No active API key configured"
        logger.warning("Agent unavailable: %s", e)
        await update.message.reply_text(  # type: ignore[union-attr]
            "⚠️ The assistant is not configured yet. Please add an API key first."
        )
    except Exception as e:
        logger.exception("Unhandled error in handle_message: %s", e)
        await update.message.reply_text(  # type: ignore[union-attr]
            "⚠️ An unexpected error occurred. Please try again."
        )
