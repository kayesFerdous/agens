import logging
from telegram import Update
from telegram.ext import ContextTypes, Application

from agent.agent import Agent
from db.database import async_session
from db import repository as session_repo
from db.models import KeyStatus
from db.repositories.api_key import APIKeyRepository

logger = logging.getLogger(__name__)


async def on_startup(app: Application) -> None:  # type: ignore[type-arg]
    """Store the shared agent in bot_data so every handler can reach it."""
    logger.info("Telegram bot ready (agent already attached)")


async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(  # type: ignore[union-attr]
        "Hello! I'm your assistant. Send me anything and I'll help you out."
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(  # type: ignore[union-attr]
        "Just send me a message and I'll do my best to help!"
    )


async def get_keys_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /keys command: list registered API keys."""
    async with async_session() as db:
        repo = APIKeyRepository(db)
        keys = await repo.list_keys()

    if not keys:
        await update.message.reply_text("No API keys found.")  # type: ignore[union-attr]
        return

    response = "🔑 *Registered API Keys*\n\n"
    for k in keys:
        status_emoji = {
            KeyStatus.ACTIVE: "✅",
            KeyStatus.RATE_LIMITED: "⏳",
            KeyStatus.EXHAUSTED: "🛑",
            KeyStatus.INVALID: "❌",
            KeyStatus.INACTIVE: "💤",
        }.get(k.status, "❓")

        response += (
            f"🆔 `{k.id}`\n"
            f"🏷 *Name:* {k.label or 'N/A'}\n"
            f"💡 *Hint:* `{k.key_hint}`\n"
            f"🚦 *Status:* {status_emoji} {k.status.value}\n"
            "───────────────────\n"
        )

    await update.message.reply_markdown(response)  # type: ignore[union-attr]


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
        logger.exception("Unhandled error in handle_message: %s", e)
        await update.message.reply_text(  # type: ignore[union-attr]
            "⚠️ An unexpected error occurred. Please try again."
        )