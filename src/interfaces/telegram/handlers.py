import logging
from telegram import Update
from telegram.ext import ContextTypes, Application

from agent.agent import Agent, Channel
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
    help_text = (
        "🤖 *Assistant Help*\n\n"
        "I'm an AI assistant with access to various tools to help you out.\n"
        "Just send me a message and I'll do my best to assist you.\n\n"
        "🛠 *Available Commands*\n"
        "• /start — Start a new session with the bot\n"
        "• /help — Show this help message\n"
        "• /api_keys — View all registered API keys and their statuses\n\n"
        "💬 *How to use*\n"
        "You don't need commands for most things! Just chat with me normally."
    )
    await update.message.reply_markdown(help_text)  # type: ignore[union-attr]


async def get_keys_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /keys command: list registered API keys."""
    async with async_session() as db:
        repo = APIKeyRepository(db)
        keys = await repo.list_keys()

    if not keys:
        await update.message.reply_text("No API keys registered yet.")
        return

    status_badge = {
        KeyStatus.ACTIVE:       "🟢 Active",
        KeyStatus.RATE_LIMITED: "🟡 Rate limited",
        KeyStatus.EXHAUSTED:    "🔴 Exhausted",
        KeyStatus.INVALID:      "❌ Invalid",
        KeyStatus.INACTIVE:     "⚪️ Inactive",
    }

    lines = [f"🔑 *API Keys* — {len(keys)} registered\n"]

    for k in keys:
        badge = status_badge.get(k.status, "❓ Unknown")
        name  = k.label or "Unnamed"
        hint  = f"`{k.key_hint}`"
        uid   = f"`...{str(k.id)[-8:]}`"   # show only last 8 chars

        lines.append(
            f"*{name}* {badge}\n"
            f"ID {uid}  ·  Hint {hint}\n"
        )

    await update.message.reply_markdown("\n".join(lines))


def _format_tool_call(tool_name: str, arguments: dict) -> str:
    """Format a tool_start event into a readable Telegram Markdown message."""
    lines = [f"🔧 *Calling:* `{tool_name}`"]
    if arguments:
        for key, value in arguments.items():
            display = str(value)
            if len(display) > 200:
                display = display[:197] + "…"
            lines.append(f"  • *{key}:* `{display}`")
    return "\n".join(lines)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_text: str = update.message.text
    user_id: int = update.effective_user.id  # type: ignore[union-attr]
    agent: Agent = ctx.bot_data["agent"]
    chat_id: int = update.effective_chat.id  # type: ignore[union-attr]

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Retrieve or create a persistent DB session for this Telegram user.
        if "session_id" not in ctx.user_data:  # type: ignore[union-attr]
            async with async_session() as db:
                session = await session_repo.insert_session(
                    db, title=f"Telegram user {user_id}"
                )
            ctx.user_data["session_id"] = session.id  # type: ignore[union-attr]
            logger.info("Created DB session %s for Telegram user %d", session.id, user_id)

        session_id: str = ctx.user_data["session_id"]  # type: ignore[union-attr]

        # Collect the full answer from the streaming ReAct loop.
        answer_parts: list[str] = []
        async for event in agent.chat(user_text, session_id, channel=Channel.TELEGRAM):
            if event.type == "tool_start":
                await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
                tool_msg = _format_tool_call(
                    event.tool or "unknown",
                    event.arguments or {},
                )
                await update.message.reply_markdown(tool_msg)  # type: ignore[union-attr]
            elif event.type == "token" and event.content:
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
