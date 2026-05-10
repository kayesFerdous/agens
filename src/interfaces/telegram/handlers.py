import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes, Application

from agent.agent import Agent, Channel
from core.model_catalog import ALL_MODELS, get_model_label, resolve_model
from db.database import async_session
from db import repository as session_repo
from db.models import KeyStatus
from db.repositories.api_key import APIKeyRepository
from .prefs import get_selected_model, set_selected_model

logger = logging.getLogger(__name__)

MODEL_CALLBACK_PREFIX = "model:"


async def on_startup(app: Application) -> None:  # type: ignore[type-arg]
    """Store the shared agent in bot_data so every handler can reach it."""
    logger.info("Telegram bot ready (agent already attached)")


async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    model_name = None
    if update.effective_user:
        model_name = get_selected_model(update.effective_user.id)
    model_label = get_model_label(model_name) if model_name else "the default model"
    await update.message.reply_text(  # type: ignore[union-attr]
        f"Hello! I'm your assistant. Send me anything and I'll help you out.\n\n"
        f"Current model: {model_label}\n"
        "Use /model to change it.",
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    def _md(text: str) -> str:
        return escape_markdown(text, version=2)

    lines = [
        f"*{_md('Assistant Help')}*",
        "",
        _md("I'm an AI assistant with access to various tools to help you out."),
        _md("Just send me a message and I'll do my best to assist you."),
        "",
        f"*{_md('Available Commands')}*",
        f"• *{_md('/start')}* — {_md('Start a new session with the bot')}",
        f"• *{_md('/help')}* — {_md('Show this help message')}",
        f"• *{_md('/model')}* — {_md('Choose a model')}",
        f"• *{_md('/api_keys')}* — {_md('View all registered API keys and their statuses')}",
        "",
        f"*{_md('How to use')}*",
        _md("You don't need commands for most things! Just chat with me normally."),
        _md("If you want a different model, tap /model and pick one from the list."),
    ]

    await update.message.reply_text(  # type: ignore[union-attr]
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


def _current_model_for_user(update: Update) -> str | None:
    if not update.effective_user:
        return None
    return get_selected_model(update.effective_user.id)


def _build_model_keyboard(current_model: str | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for model_id, label, _ in ALL_MODELS:
        prefix = "✅ " if model_id == current_model else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{prefix}{label}",
                callback_data=f"{MODEL_CALLBACK_PREFIX}{model_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="Close", callback_data=f"{MODEL_CALLBACK_PREFIX}close")])
    return InlineKeyboardMarkup(rows)


def _render_model_prompt(current_model: str | None) -> str:
    if current_model:
        return (
            f"Current model: {get_model_label(current_model)}\n\n"
            "Tap a model below to change it."
        )
    return (
        "No model is pinned for this chat yet.\n\n"
        "Tap a model below to set one, or keep using the default model."
    )


async def model_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = (update.message.text or "").strip() if update.message else ""
    command_parts = message_text.split(maxsplit=1)
    current_model = _current_model_for_user(update)

    if len(command_parts) > 1:
        choice = command_parts[1].strip()
        lowered = choice.lower()
        if lowered not in {"list", "show", "picker", "choose"}:
            resolved = resolve_model(choice)
            if resolved:
                if update.effective_user:
                    set_selected_model(update.effective_user.id, resolved)
                await update.message.reply_text(  # type: ignore[union-attr]
                    f"Model set to {get_model_label(resolved)}. New chats will use this model."
                )
                return

    current_model = _current_model_for_user(update)
    await update.message.reply_text(  # type: ignore[union-attr]
        _render_model_prompt(current_model),
        reply_markup=_build_model_keyboard(current_model),
    )


async def handle_model_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(MODEL_CALLBACK_PREFIX):
        return

    await query.answer()
    selection = query.data[len(MODEL_CALLBACK_PREFIX):]

    if selection == "close":
        await query.edit_message_text("Model picker closed.")
        return

    resolved = resolve_model(selection)
    if not resolved:
        await query.answer("That model is not available.", show_alert=True)
        return

    user = update.effective_user
    if not user:
        await query.answer("Unable to identify the Telegram user.", show_alert=True)
        return

    current_model = get_selected_model(user.id)
    if current_model == resolved:
        await query.answer(f"Already using {get_model_label(resolved)}")
        return

    set_selected_model(user.id, resolved)
    await query.edit_message_text(
        f"Model set to {get_model_label(resolved)}. New chats will use this model.",
        reply_markup=_build_model_keyboard(resolved),
    )
    await query.answer(f"Model set to {get_model_label(resolved)}")


async def get_keys_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /keys command: list registered API keys."""
    async with async_session() as db:
        repo = APIKeyRepository(db)
        keys = await repo.list_keys()

    if not keys:
        await update.message.reply_text("No API keys registered yet.")  # type: ignore[union-attr]
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

    await update.message.reply_markdown("\n".join(lines))  # type: ignore[union-attr]


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
    selected_model = get_selected_model(user_id)

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
        async for event in agent.chat(
            user_text,
            session_id,
            channel=Channel.TELEGRAM,
            model=selected_model,
        ):
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
