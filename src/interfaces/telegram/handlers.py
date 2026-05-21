import asyncio
from dataclasses import dataclass
import logging
import re
from datetime import datetime
from html import escape as html_escape, unescape

import markdown
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes, Application

from agent.agent import Agent, Channel
from core.tool_groups import DEFAULT_TOOL_GROUPS
from db.database import async_session
from db import repository as session_repo
from db.models import APIKey, KeyStatus
from db.repositories.api_key import APIKeyRepository
from interfaces.web.api.models.router import list_models
from interfaces.web.api.models.schemas import ModelInfo, ModelsResponse, ProviderModels
from interfaces.api_key_state import (
    NO_API_KEYS_TELEGRAM_MESSAGE,
    has_any_api_keys,
    user_key_unavailable_message,
)
from llm.catalog import get_catalog
from .prefs import get_selected_model, set_selected_model, get_tool_groups, set_tool_groups

logger = logging.getLogger(__name__)

MODEL_CALLBACK_PREFIX    = "model:"
TOOLS_CALLBACK_PREFIX    = "tools:"
KEY_TOGGLE_CALLBACK_PREFIX = "keytoggle:"
KEY_BULK_CALLBACK_PREFIX   = "keybulk:"
TELEGRAM_PLACEHOLDER_TEXT = "Thinking..."
TELEGRAM_RESPONSE_CHUNK_LIMIT = 3200
TELEGRAM_HTML_TAGS = {
    "a",
    "b",
    "code",
    "del",
    "i",
    "pre",
    "s",
    "span",
    "strike",
    "tg-spoiler",
    "u",
}
MODEL_CALLBACK_CLOSE = "close"
MODEL_CALLBACK_AUTO = "auto"
MODEL_CALLBACK_BACK = "back"
MODEL_CALLBACK_PROVIDER_PREFIX = "provider:"
MODEL_CALLBACK_SET_PREFIX = "set:"
PROVIDER_NAME_FALLBACKS = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "groq": "Groq",
    "cerebras": "Cerebras",
    "siliconflow": "SiliconFlow",
    "deepseek": "DeepSeek"
}


@dataclass(frozen=True)
class TelegramModelOption:
    value: str
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str
    status: str
    cooldown_until_ts: int | None
    has_active_key: bool


def _md(text: str) -> str:
    return escape_markdown(text, version=2)


async def on_startup(app: Application) -> None:  # type: ignore[type-arg]
    """Store the shared agent in bot_data so every handler can reach it."""
    logger.info("Telegram bot ready (agent already attached)")


async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Telegram framework errors without turning network blips into tracebacks."""
    error = ctx.error
    if isinstance(error, RetryAfter):
        logger.warning("Telegram rate limit from framework; retry_after=%s", error.retry_after)
        return
    if isinstance(error, (TimedOut, NetworkError)):
        logger.warning("Telegram network timeout from framework: %s", error)
        return
    if isinstance(error, BaseException):
        logger.error(
            "Unhandled Telegram framework error",
            exc_info=(type(error), error, error.__traceback__),
        )
        return
    logger.error("Unhandled Telegram framework error: %r", error)


async def start_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as db:
        if not await has_any_api_keys(APIKeyRepository(db)):
            await update.message.reply_text(NO_API_KEYS_TELEGRAM_MESSAGE)  # type: ignore[union-attr]
            return

    model_name = None
    if update.effective_user:
        model_name = get_selected_model(update.effective_user.id)
    model_label = _get_selected_model_label(model_name)
    await update.message.reply_text(  # type: ignore[union-attr]
        "\n".join([
            "*Assistant ready*",
            "",
            _md("Send me anything and I'll help you out."),
            f"*{_md('Current model:')}* `{_md(model_label)}`",
            _md("Use /model to change it."),
        ]),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
        f"• *{_md('/tools')}* — {_md('Select enabled tools')}",
        f"• *{_md('/keys')}* — {_md('View API keys and toggle status')}",
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


def _get_selected_model_label(selected_model: str | None) -> str:
    if not selected_model:
        return "Auto (best available)"
    if "/" not in selected_model:
        return selected_model
    provider_id, model_id = selected_model.split("/", maxsplit=1)
    for entry in get_catalog():
        if entry.provider == provider_id and entry.id == model_id:
            provider_name = PROVIDER_NAME_FALLBACKS.get(provider_id, provider_id)
            return f"{provider_name} / {entry.name}"
    return selected_model


async def _load_models_response() -> ModelsResponse:
    async with async_session() as db:
        return await list_models(db)


def _flatten_model_options(model_data: ModelsResponse) -> list[TelegramModelOption]:
    options: list[TelegramModelOption] = []
    for provider in model_data.providers:
        for model in provider.models:
            options.append(
                TelegramModelOption(
                    value=f"{provider.id}/{model.id}",
                    provider_id=provider.id,
                    provider_name=provider.name,
                    model_id=model.id,
                    model_name=model.name,
                    status=model.status,
                    cooldown_until_ts=model.cooldown_until_ts,
                    has_active_key=provider.has_active_key,
                )
            )
    return options


def _find_provider(model_data: ModelsResponse, provider_id: str) -> ProviderModels | None:
    return next((provider for provider in model_data.providers if provider.id == provider_id), None)


def _find_model_option(
    model_data: ModelsResponse,
    selected_value: str,
) -> TelegramModelOption | None:
    for option in _flatten_model_options(model_data):
        if option.value == selected_value:
            return option
    return None


def _find_model_matches(query: str, options: list[TelegramModelOption]) -> list[TelegramModelOption]:
    value = query.strip().lower()
    if not value:
        return []

    exact: list[TelegramModelOption] = []
    for option in options:
        aliases = {
            option.value.lower(),
            option.model_id.lower(),
            option.model_name.lower(),
            f"{option.provider_id}/{option.model_name}".lower(),
            f"{option.provider_name}/{option.model_name}".lower(),
        }
        if value in aliases:
            exact.append(option)
    if exact:
        return exact

    partial: list[TelegramModelOption] = []
    for option in options:
        haystack = " ".join([
            option.value,
            option.provider_id,
            option.provider_name,
            option.model_id,
            option.model_name,
        ]).lower()
        if value in haystack:
            partial.append(option)
    return partial


def _model_status_icon(model: ModelInfo, *, has_active_key: bool) -> str:
    if not has_active_key or model.status == "no_key":
        return "🔒"
    if model.status == "cooldown":
        return "⏳"
    return "🟢"


def _trim_button_text(text: str, max_chars: int = 56) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _format_cooldown_time(cooldown_until_ts: int | None) -> str | None:
    if cooldown_until_ts is None:
        return None
    dt = datetime.fromtimestamp(cooldown_until_ts)
    return dt.strftime("%H:%M")


def _build_model_root_keyboard(current_model: str | None, model_data: ModelsResponse) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    auto_prefix = "✅ " if current_model is None else ""
    rows.append([
        InlineKeyboardButton(
            text=f"{auto_prefix}✨ Auto (best available)",
            callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_AUTO}",
        )
    ])

    for provider in model_data.providers:
        provider_prefix = "✅ " if current_model and current_model.startswith(f"{provider.id}/") else ""
        availability = "🟢" if provider.has_active_key else "🔒"
        label = _trim_button_text(f"{provider_prefix}{availability} {provider.name} ({len(provider.models)})")
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_PROVIDER_PREFIX}{provider.id}",
            )
        ])
    rows.append([InlineKeyboardButton(
        text="✕ Close",
        callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_CLOSE}",
    )])
    return InlineKeyboardMarkup(rows)


def _build_provider_model_keyboard(
    provider: ProviderModels,
    current_model: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    auto_prefix = "✅ " if current_model is None else ""
    rows.append([InlineKeyboardButton(
        text=f"{auto_prefix}✨ Auto (best available)",
        callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_AUTO}",
    )])
    for model in provider.models:
        value = f"{provider.id}/{model.id}"
        prefix = "✅ " if value == current_model else ""
        status = _model_status_icon(model, has_active_key=provider.has_active_key)
        free_badge = " · free" if model.free_tier else ""
        text = _trim_button_text(f"{prefix}{status} {model.name}{free_badge}")
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_SET_PREFIX}{value}",
        )])

    rows.append([
        InlineKeyboardButton(
            text="← Providers",
            callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_BACK}",
        ),
        InlineKeyboardButton(
            text="✕ Close",
            callback_data=f"{MODEL_CALLBACK_PREFIX}{MODEL_CALLBACK_CLOSE}",
        ),
    ])
    return InlineKeyboardMarkup(rows)


def _render_model_root_prompt(current_model: str | None) -> str:
    return "\n".join([
        f"*{_md('Model Selection')}*",
        "",
        f"*{_md('Current model:')}* `{_md(_get_selected_model_label(current_model))}`",
        _md("Choose a provider below, or pick Auto to let Agens choose the best available model."),
    ])


def _render_provider_prompt(provider: ProviderModels, current_model: str | None) -> str:
    ready_count = sum(1 for model in provider.models if model.status == "available")
    cooldown_count = sum(1 for model in provider.models if model.status == "cooldown")
    unavailable_count = sum(
        1 for model in provider.models if model.status == "no_key" or not provider.has_active_key
    )
    lines = [
        f"*{_md(provider.name)}*",
        "",
        f"*{_md('Current model:')}* `{_md(_get_selected_model_label(current_model))}`",
        "",
        _md(
            f"{ready_count} ready · {cooldown_count} cooling down · {unavailable_count} unavailable"
        ),
        _md("Legend: 🟢 ready · ⏳ cooling down · 🔒 unavailable"),
    ]
    if not provider.has_active_key:
        lines.extend([
            "",
            _md(f"No active {provider.name} key found. Use /keys to enable or add one."),
        ])
    return "\n".join(lines)


def _render_model_updated_message(
    label: str,
    *,
    auto_mode: bool = False,
    cooldown_until_ts: int | None = None,
) -> str:
    if auto_mode:
        return "\n".join([
            "*Model updated*",
            "",
            _md("Now using Auto mode."),
            _md("Agens will pick the best available model for each new request."),
        ])

    lines = [
        "*Model updated*",
        "",
        _md(f"Now using {label}."),
    ]
    cooldown = _format_cooldown_time(cooldown_until_ts)
    if cooldown:
        lines.append(_md(f"Heads up: this model is cooling down until about {cooldown}."))
    else:
        lines.append(_md("New chats will use this model."))
    return "\n".join(lines)


def _render_model_not_found_message(choice: str) -> str:
    return "\n".join([
        "*Model not found*",
        "",
        _md(f"I could not find a model matching: {choice}"),
        _md("Try a more specific query or pick from the interactive list below."),
    ])


def _render_model_ambiguous_message(choice: str, matches: list[TelegramModelOption]) -> str:
    lines = [
        "*Multiple matches found*",
        "",
        _md(f"Your query '{choice}' matches several models:"),
    ]
    for option in matches[:5]:
        lines.append(f"• `{_md(option.value)}` — {_md(option.model_name)}")
    lines.extend([
        "",
        _md("Use /model with the full provider/model id, or pick from the list below."),
    ])
    return "\n".join(lines)


async def _send_model_root_picker(update: Update, current_model: str | None) -> None:
    model_data = await _load_models_response()
    await update.message.reply_text(  # type: ignore[union-attr]
        _render_model_root_prompt(current_model),
        reply_markup=_build_model_root_keyboard(current_model, model_data),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


def _is_auto_choice(value: str) -> bool:
    return value.strip().lower() in {"auto", "default", "router", "best"}


def _is_picker_choice(value: str) -> bool:
    return value.strip().lower() in {"list", "show", "picker", "choose", "open"}


async def _handle_direct_model_choice(
    update: Update,
    choice: str,
    current_model: str | None,
    model_data: ModelsResponse,
) -> bool:
    user = update.effective_user
    if not user:
        return False

    if _is_auto_choice(choice):
        set_selected_model(user.id, None)
        await update.message.reply_text(  # type: ignore[union-attr]
            _render_model_updated_message("Auto", auto_mode=True),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True

    options = _flatten_model_options(model_data)
    matches = _find_model_matches(choice, options)
    if len(matches) == 1:
        selected = matches[0]
        if not selected.has_active_key or selected.status == "no_key":
            await update.message.reply_text(  # type: ignore[union-attr]
                "\n".join([
                    "*Model unavailable*",
                    "",
                    _md(f"{selected.provider_name} has no active key for {selected.model_name}."),
                    _md("Use /keys to enable a key, then try again."),
                ]),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            await _send_model_root_picker(update, current_model)
            return True

        set_selected_model(user.id, selected.value)
        await update.message.reply_text(  # type: ignore[union-attr]
            _render_model_updated_message(
                _get_selected_model_label(selected.value),
                cooldown_until_ts=selected.cooldown_until_ts,
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True

    if len(matches) > 1:
        await update.message.reply_text(  # type: ignore[union-attr]
            _render_model_ambiguous_message(choice, matches),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await _send_model_root_picker(update, current_model)
        return True

    await update.message.reply_text(  # type: ignore[union-attr]
        _render_model_not_found_message(choice),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await _send_model_root_picker(update, current_model)
    return True


async def _edit_to_model_root(
    query,
    current_model: str | None,
    model_data: ModelsResponse,
) -> None:
    await query.edit_message_text(
        _render_model_root_prompt(current_model),
        reply_markup=_build_model_root_keyboard(current_model, model_data),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def _edit_to_provider_picker(
    query,
    provider: ProviderModels,
    current_model: str | None,
) -> None:
    await query.edit_message_text(
        _render_provider_prompt(provider, current_model),
        reply_markup=_build_provider_model_keyboard(provider, current_model),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


def _is_unavailable_option(option: TelegramModelOption) -> bool:
    return (not option.has_active_key) or option.status == "no_key"


async def model_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = (update.message.text or "").strip() if update.message else ""
    command_parts = message_text.split(maxsplit=1)
    current_model = _current_model_for_user(update)

    try:
        model_data = await _load_models_response()
    except Exception as exc:
        logger.warning("Could not load model picker data: %s", exc)
        await update.message.reply_text(  # type: ignore[union-attr]
            _md("Could not load model list right now. Please try again."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    if len(command_parts) > 1:
        choice = command_parts[1].strip()
        if not _is_picker_choice(choice):
            handled = await _handle_direct_model_choice(update, choice, current_model, model_data)
            if handled:
                return

    await update.message.reply_text(  # type: ignore[union-attr]
        _render_model_root_prompt(current_model),
        reply_markup=_build_model_root_keyboard(current_model, model_data),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_model_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(MODEL_CALLBACK_PREFIX):
        return

    user = update.effective_user
    if not user:
        await query.answer("Unable to identify the Telegram user.", show_alert=True)
        return

    selection = query.data[len(MODEL_CALLBACK_PREFIX):]

    if selection == MODEL_CALLBACK_CLOSE:
        await query.edit_message_text(
            "*Model picker closed*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await query.answer()
        return

    try:
        model_data = await _load_models_response()
    except Exception as exc:
        logger.warning("Could not load model picker data: %s", exc)
        await query.answer("Could not load models right now.", show_alert=True)
        return

    current_model = get_selected_model(user.id)

    if selection in {MODEL_CALLBACK_BACK, ""}:
        await _edit_to_model_root(query, current_model, model_data)
        await query.answer()
        return

    if selection == MODEL_CALLBACK_AUTO:
        if current_model is None:
            await query.answer("Already using Auto mode.")
            return
        set_selected_model(user.id, None)
        await _edit_to_model_root(query, None, model_data)
        await query.answer("Auto model selection enabled.")
        return

    if selection.startswith(MODEL_CALLBACK_PROVIDER_PREFIX):
        provider_id = selection[len(MODEL_CALLBACK_PROVIDER_PREFIX):]
        provider = _find_provider(model_data, provider_id)
        if provider is None:
            await query.answer("That provider is not available.", show_alert=True)
            return
        await _edit_to_provider_picker(query, provider, current_model)
        await query.answer()
        return

    if selection.startswith(MODEL_CALLBACK_SET_PREFIX):
        selected_value = selection[len(MODEL_CALLBACK_SET_PREFIX):]
        option = _find_model_option(model_data, selected_value)
        if option is None:
            await query.answer("That model is not available.", show_alert=True)
            return

        provider = _find_provider(model_data, option.provider_id)
        if provider is None:
            await query.answer("That model provider is not available.", show_alert=True)
            return

        if _is_unavailable_option(option):
            await query.answer(
                f"No active {option.provider_name} key for this model. Use /keys.",
                show_alert=True,
            )
            return

        if current_model == option.value:
            await query.answer(f"Already using {option.model_name}.")
            return

        set_selected_model(user.id, option.value)
        await _edit_to_provider_picker(query, provider, option.value)
        if option.cooldown_until_ts:
            cooldown = _format_cooldown_time(option.cooldown_until_ts) or "soon"
            await query.answer(f"Set to {option.model_name} (cooling down until ~{cooldown}).")
        else:
            await query.answer(f"Model set to {option.model_name}.")
        return

    await query.answer("Unknown model action.", show_alert=True)
    return


# ── /tools ─────────────────────────────────────────────────────────────────────

def _build_tools_keyboard(current_groups: dict[str, bool]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for group_id in DEFAULT_TOOL_GROUPS:
        is_enabled = current_groups.get(group_id, DEFAULT_TOOL_GROUPS[group_id])
        prefix = "✅ " if is_enabled else "❌ "
        rows.append([
            InlineKeyboardButton(
                text=f"{prefix}{group_id}",
                callback_data=f"{TOOLS_CALLBACK_PREFIX}{group_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="Close", callback_data=f"{TOOLS_CALLBACK_PREFIX}close")])
    return InlineKeyboardMarkup(rows)


def _render_tools_prompt() -> str:
    return (
        f"*{_md('Tool Groups')}*\n\n"
        f"{_md('Tap a tool group below to toggle it on or off.')}\n"
        f"{_md('Web group includes web_search + web_fetch.')}"
    )


async def tools_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    current_groups = get_tool_groups(update.effective_user.id)
    await update.message.reply_text(  # type: ignore[union-attr]
        _render_tools_prompt(),
        reply_markup=_build_tools_keyboard(current_groups),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_tools_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(TOOLS_CALLBACK_PREFIX):
        return

    await query.answer()
    selection = query.data[len(TOOLS_CALLBACK_PREFIX):]

    if selection == "close":
        await query.edit_message_text(
            "*Tool picker closed*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    user = update.effective_user
    if not user:
        await query.answer("Unable to identify the Telegram user.", show_alert=True)
        return

    if selection not in DEFAULT_TOOL_GROUPS:
        await query.answer("Unknown tool group.", show_alert=True)
        return

    current_groups = get_tool_groups(user.id)
    current_groups[selection] = not current_groups.get(selection, DEFAULT_TOOL_GROUPS[selection])
    set_tool_groups(user.id, current_groups)

    await query.edit_message_text(
        _render_tools_prompt(),
        reply_markup=_build_tools_keyboard(current_groups),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    status = "enabled" if current_groups[selection] else "disabled"
    await query.answer(f"Tool group {selection} {status}")


# ── /keys — helpers ────────────────────────────────────────────────────────────

def _status_dot(key: APIKey) -> str:
    return {
        KeyStatus.ACTIVE:   "🟢",
        KeyStatus.INACTIVE: "⚪",
    }.get(key.status, "🔴")


def _status_label(key: APIKey) -> str:
    raw = key.status.value.replace("_", " ")
    mapping = {
        "rate limited": "rate limited",
        "exhausted":    "exhausted",
        "invalid":      "invalid",
        "active":       "active",
        "inactive":     "inactive",
    }
    return mapping.get(raw, raw)


def _build_keys_message(keys: list[APIKey]) -> str:
    active   = [k for k in keys if k.status == KeyStatus.ACTIVE]
    inactive = [k for k in keys if k.status == KeyStatus.INACTIVE]
    broken   = [k for k in keys if k.status not in {KeyStatus.ACTIVE, KeyStatus.INACTIVE}]

    lines: list[str] = [
        f"*{_md('API Keys')}*",
        "",
        f"🟢 *{len(active)}* active   "
        f"⚪ *{len(inactive)}* inactive   "
        f"🔴 *{len(broken)}* error",
        "",
    ]

    if not keys:
        lines.append(_md("No API keys registered yet."))
        return "\n".join(lines)

    if active:
        lines.append(f"*{_md('Active')}*")
        for k in active:
            lines.append(
                f"{_status_dot(k)} `{_md(k.label or 'Unnamed')}` "
                f"_{_md(k.key_hint or '—')}_"
            )
        lines.append("")

    if inactive:
        lines.append(f"*{_md('Inactive')}*")
        for k in inactive:
            lines.append(
                f"{_status_dot(k)} `{_md(k.label or 'Unnamed')}` "
                f"_{_md(k.key_hint or '—')}_"
            )
        lines.append("")

    if broken:
        lines.append(f"*{_md('Unavailable')}*")
        lines.append(_md("These keys cannot be toggled."))
        for k in broken:
            lines.append(
                f"{_status_dot(k)} `{_md(k.label or 'Unnamed')}` "
                f"— _{_md(_status_label(k))}_"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def _build_keys_keyboard(keys: list[APIKey]) -> InlineKeyboardMarkup:
    active   = [k for k in keys if k.status == KeyStatus.ACTIVE]
    inactive = [k for k in keys if k.status == KeyStatus.INACTIVE]

    rows: list[list[InlineKeyboardButton]] = []

    for key in active:
        rows.append([
            InlineKeyboardButton(
                text=f"🔴 Disable  {key.label or 'Unnamed'}",
                callback_data=f"{KEY_TOGGLE_CALLBACK_PREFIX}{key.id}",
            )
        ])

    for key in inactive:
        rows.append([
            InlineKeyboardButton(
                text=f"🟢 Enable  {key.label or 'Unnamed'}",
                callback_data=f"{KEY_TOGGLE_CALLBACK_PREFIX}{key.id}",
            )
        ])

    bulk_row: list[InlineKeyboardButton] = []
    if inactive:
        bulk_row.append(InlineKeyboardButton(
            text="🟢 Enable all",
            callback_data=f"{KEY_BULK_CALLBACK_PREFIX}enable_all",
        ))
    if active:
        bulk_row.append(InlineKeyboardButton(
            text="🔴 Disable all",
            callback_data=f"{KEY_BULK_CALLBACK_PREFIX}disable_all",
        ))
    if bulk_row:
        rows.append(bulk_row)

    rows.append([InlineKeyboardButton(
        text="✕  Close",
        callback_data=f"{KEY_TOGGLE_CALLBACK_PREFIX}close",
    )])

    return InlineKeyboardMarkup(rows)


# ── /keys — command handler ────────────────────────────────────────────────────

async def get_keys_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /keys — grouped key manager with stats and bulk actions."""
    async with async_session() as db:
        repo = APIKeyRepository(db)
        keys = await repo.list_keys()

    await update.message.reply_text(  # type: ignore[union-attr]
        _build_keys_message(keys),
        reply_markup=_build_keys_keyboard(keys),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /keys — per-key toggle callback ───────────────────────────────────────────

async def handle_key_toggle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(KEY_TOGGLE_CALLBACK_PREFIX):
        return

    selection = query.data[len(KEY_TOGGLE_CALLBACK_PREFIX):]

    if selection == "close":
        await query.answer()
        await query.edit_message_text(
            f"*{_md('Key manager closed')}*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    async with async_session() as db:
        repo = APIKeyRepository(db)
        key  = await repo.get_by_id(selection)

        if not key:
            await query.answer("Key not found.", show_alert=True)
            return

        if key.status not in {KeyStatus.ACTIVE, KeyStatus.INACTIVE}:
            await query.answer(
                f"This key is {_status_label(key)} and cannot be toggled.",
                show_alert=True,
            )
            return

        new_status = KeyStatus.INACTIVE if key.status == KeyStatus.ACTIVE else KeyStatus.ACTIVE
        await repo.update_status(key.id, new_status)
        keys = await repo.list_keys()

    action = "disabled" if new_status == KeyStatus.INACTIVE else "enabled"
    await query.answer(f"{key.label or 'Key'} {action}.")
    await query.edit_message_text(
        _build_keys_message(keys),
        reply_markup=_build_keys_keyboard(keys),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── /keys — bulk toggle callback ───────────────────────────────────────────────

async def handle_key_bulk_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the 'Enable all' / 'Disable all' buttons.

    Register in your dispatcher:
        application.add_handler(CallbackQueryHandler(
            handle_key_bulk_callback, pattern=f"^{KEY_BULK_CALLBACK_PREFIX}"
        ))
    """
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(KEY_BULK_CALLBACK_PREFIX):
        return

    action = query.data[len(KEY_BULK_CALLBACK_PREFIX):]

    async with async_session() as db:
        repo = APIKeyRepository(db)
        keys = await repo.list_keys()

        if action == "enable_all":
            targets    = [k for k in keys if k.status == KeyStatus.INACTIVE]
            new_status = KeyStatus.ACTIVE
            verb       = "enabled"
        elif action == "disable_all":
            targets    = [k for k in keys if k.status == KeyStatus.ACTIVE]
            new_status = KeyStatus.INACTIVE
            verb       = "disabled"
        else:
            await query.answer("Unknown action.", show_alert=True)
            return

        if not targets:
            await query.answer("Nothing to change.")
            return

        for key in targets:
            await repo.update_status(key.id, new_status)

        keys = await repo.list_keys()

    await query.answer(f"{len(targets)} key(s) {verb}.")
    await query.edit_message_text(
        _build_keys_message(keys),
        reply_markup=_build_keys_keyboard(keys),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ── message handler ────────────────────────────────────────────────────────────

def _format_tool_call(tool_name: str, arguments: dict) -> str:
    """Format a tool_start event into a readable Telegram Markdown message."""
    lines = [f"*Called:* `{escape_markdown(tool_name, version=2)}`"]
    if arguments:
        for key, value in arguments.items():
            display = str(value)
            if len(display) > 200:
                display = display[:197] + "…"
            lines.append(
                f"  • *{escape_markdown(str(key), version=2)}:* `{escape_markdown(display, version=2)}`"
            )
    return "\n".join(lines)


def _normalize_telegram_html(html: str) -> str:
    """Convert Python-Markdown HTML into the subset accepted by Telegram."""
    html = html.replace("<strong>", "<b>").replace("</strong>", "</b>")
    html = html.replace("<em>", "<i>").replace("</em>", "</i>")
    html = re.sub(r"<code\b[^>]*>", "<code>", html)
    html = re.sub(r"<pre\b[^>]*>", "<pre>", html)

    def _render_heading(match: re.Match[str]) -> str:
        content = match.group(2).strip()
        if not content:
            return ""
        return f"<b>{content}</b>\n\n"

    html = re.sub(r"<h([1-6])>(.*?)</h\1>", _render_heading, html, flags=re.S)

    def _render_blockquote(match: re.Match[str]) -> str:
        content = match.group(1)
        content = content.replace("<p>", "").replace("</p>", "\n")
        content = re.sub(r"<br\s*/?>", "\n", content)
        content = content.strip()
        if not content:
            return ""
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return "\n".join(f"&gt; {line}" for line in lines) + "\n"

    html = re.sub(r"<blockquote>(.*?)</blockquote>", _render_blockquote, html, flags=re.S)

    def _clean_list_item(item: str) -> str:
        item = item.replace("<p>", "").replace("</p>", "\n")
        item = re.sub(r"<br\s*/?>", "\n", item)
        lines = [line.strip() for line in item.splitlines() if line.strip()]
        return " ".join(lines)

    def _render_ol(match: re.Match[str]) -> str:
        body = match.group(1)
        items = re.findall(r"<li>(.*?)</li>", body, flags=re.S)
        lines: list[str] = []
        for index, item in enumerate(items, 1):
            cleaned = _clean_list_item(item)
            if cleaned:
                lines.append(f"{index}. {cleaned}")
        return "\n".join(lines)

    def _render_ul(match: re.Match[str]) -> str:
        body = match.group(1)
        items = re.findall(r"<li>(.*?)</li>", body, flags=re.S)
        lines: list[str] = []
        for item in items:
            cleaned = _clean_list_item(item)
            if cleaned:
                lines.append(f"• {cleaned}")
        return "\n".join(lines)

    html = re.sub(r"<ol>(.*?)</ol>", _render_ol, html, flags=re.S)
    html = re.sub(r"<ul>(.*?)</ul>", _render_ul, html, flags=re.S)
    html = re.sub(r"</?li>", "", html)

    html = re.sub(r"</?thead>|</?tbody>|</?tfoot>", "", html)
    html = re.sub(r"<table\b[^>]*>", "", html)
    html = html.replace("</table>", "")
    html = re.sub(r"<tr\b[^>]*>", "", html)
    html = html.replace("</tr>", "\n")
    html = re.sub(r"<th\b[^>]*>", "", html)
    html = html.replace("</th>", "  ")
    html = re.sub(r"<td\b[^>]*>", "", html)
    html = html.replace("</td>", "  ")

    html = html.replace("<p>", "").replace("</p>", "\n")
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"<hr\s*/?>", "\n", html)

    def _strip_unsupported_tag(match: re.Match[str]) -> str:
        return match.group(0) if match.group(1).lower() in TELEGRAM_HTML_TAGS else ""

    html = re.sub(
        r"</?([A-Za-z][A-Za-z0-9-]*)(?:\s[^>]*)?>",
        _strip_unsupported_tag,
        html,
    )
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def _render_telegram_html(markdown_text: str) -> str:
    html = markdown.markdown(
        markdown_text,
        extensions=["fenced_code", "tables"],
        output_format="html",
    )
    return _normalize_telegram_html(html)


def _strip_html_to_text(html_text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html_text)).strip()


def _split_telegram_html(html_text: str, limit: int = TELEGRAM_RESPONSE_CHUNK_LIMIT) -> list[str]:
    """Split final Telegram HTML without cutting through tags or entities."""
    html_text = html_text.strip()
    if not html_text:
        return []
    if len(html_text) <= limit:
        return [html_text]

    chunks: list[str] = []
    current = ""
    open_tags: list[tuple[str, str]] = []
    token_pattern = re.compile(r"(<[^>]+>|&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]+);)")
    tag_pattern = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)(?:\s[^>]*)?>")

    def closing_markup() -> str:
        return "".join(f"</{name}>" for name, _ in reversed(open_tags))

    def opening_markup() -> str:
        return "".join(opener for _, opener in open_tags)

    def flush() -> None:
        nonlocal current
        text = current + closing_markup()
        if text.strip():
            chunks.append(text)
        current = opening_markup()

    def apply_tag_state(token: str) -> None:
        match = tag_pattern.fullmatch(token)
        if not match:
            return
        name = match.group(1).lower()
        if name not in TELEGRAM_HTML_TAGS:
            return
        is_closing = token.startswith("</")
        is_self_closing = token.endswith("/>")
        if is_closing:
            for index in range(len(open_tags) - 1, -1, -1):
                if open_tags[index][0] == name:
                    del open_tags[index:]
                    break
        elif not is_self_closing:
            open_tags.append((name, token))

    def append_text(token: str) -> None:
        nonlocal current
        while token:
            available = limit - len(current) - len(closing_markup())
            if available <= 0:
                flush()
                available = limit - len(current) - len(closing_markup())
            piece = token[:available]
            current += piece
            token = token[available:]
            if token:
                flush()

    for token in filter(None, token_pattern.split(html_text)):
        if token.startswith("<"):
            if len(current) + len(token) + len(closing_markup()) > limit and current.strip():
                flush()
            current += token
            apply_tag_state(token)
            continue

        if token.startswith("&") and token.endswith(";"):
            if len(current) + len(token) + len(closing_markup()) > limit and current.strip():
                flush()
            current += token
            continue

        append_text(token)

    if current.strip():
        chunks.append(current + closing_markup())

    return chunks


async def _safe_edit_html(message, html_text: str, *, retry: bool = True) -> str:
    try:
        await message.edit_text(html_text, parse_mode=ParseMode.HTML)
        return html_text
    except BadRequest as exc:
        logger.warning("Telegram rejected rendered HTML; sending unformatted text: %s", exc)
        await message.edit_text(_strip_html_to_text(html_text) or "I could not format that response.")
        return html_text
    except RetryAfter as exc:
        logger.warning("Telegram rate-limited message edit; retry_after=%s", exc.retry_after)
        if retry and exc.retry_after <= 5:
            await asyncio.sleep(exc.retry_after)
            return await _safe_edit_html(message, html_text, retry=False)
        return html_text
    except (TimedOut, NetworkError) as exc:
        logger.warning("Telegram message edit failed due to network issue: %s", exc)
        return html_text


async def _safe_reply_html(message, html_text: str, *, retry: bool = True) -> None:
    try:
        await message.reply_text(html_text, parse_mode=ParseMode.HTML)
    except BadRequest as exc:
        logger.warning("Telegram rejected rendered HTML chunk; sending unformatted text: %s", exc)
        await message.reply_text(_strip_html_to_text(html_text) or "I could not format that response.")
    except RetryAfter as exc:
        logger.warning("Telegram rate-limited message send; retry_after=%s", exc.retry_after)
        if retry and exc.retry_after <= 5:
            await asyncio.sleep(exc.retry_after)
            await _safe_reply_html(message, html_text, retry=False)
    except (TimedOut, NetworkError) as exc:
        logger.warning("Telegram message send failed due to network issue: %s", exc)


async def _deliver_final_response(message, placeholder, response_text: str) -> None:
    final_text = response_text.strip() or "I'm not sure how to answer that."
    try:
        rendered = _render_telegram_html(final_text)
    except Exception as exc:
        logger.warning("Failed to render Telegram Markdown; sending unformatted text: %s", exc)
        rendered = html_escape(final_text)

    chunks = _split_telegram_html(rendered) or [html_escape(final_text)]
    await _safe_edit_html(placeholder, chunks[0])
    for chunk in chunks[1:]:
        await _safe_reply_html(message, chunk)


async def _typing_indicator_loop(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    try:
        while True:
            await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug("Telegram typing indicator failed: %s", exc)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not update.effective_user:
        return

    user_text: str = update.message.text
    user_id: int = update.effective_user.id
    agent: Agent = ctx.bot_data["agent"]
    chat_id: int = update.effective_chat.id  # type: ignore[union-attr]
    selected_model = get_selected_model(user_id)
    tool_groups = get_tool_groups(user_id)

    async with async_session() as db:
        if not await has_any_api_keys(APIKeyRepository(db)):
            await update.message.reply_text(NO_API_KEYS_TELEGRAM_MESSAGE)
            return

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
    placeholder = None
    typing_task: asyncio.Task[None] | None = None

    try:
        if "session_id" not in ctx.user_data:  # type: ignore[union-attr]
            async with async_session() as db:
                session = await session_repo.insert_session(
                    db, title=f"Telegram user {user_id}"
                )
            ctx.user_data["session_id"] = session.id  # type: ignore[union-attr]
            logger.info("Created DB session %s for Telegram user %d", session.id, user_id)

        session_id: str = ctx.user_data["session_id"]  # type: ignore[union-attr]

        placeholder = await update.message.reply_text(TELEGRAM_PLACEHOLDER_TEXT)
        typing_task = asyncio.create_task(_typing_indicator_loop(ctx, chat_id))
        response_parts: list[str] = []

        async for event in agent.chat(
            user_text,
            session_id,
            channel=Channel.TELEGRAM,
            model=selected_model,
            tool_groups=tool_groups,
        ):
            if event.type == "tool_start":
                await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
                tool_msg = _format_tool_call(
                    event.tool or "unknown",
                    event.arguments or {},
                )
                await update.message.reply_text(
                    tool_msg,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )

            elif event.type == "token" and event.content:
                response_parts.append(event.content)

            elif event.type == "error" and event.error:
                logger.error("Agent error: %s", event.error)
                error_text = _md(user_key_unavailable_message(event.error))
                if placeholder:
                    await placeholder.edit_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
                else:
                    await update.message.reply_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
                return

        await _deliver_final_response(
            update.message,
            placeholder,
            "".join(response_parts),
        )

    except RuntimeError as e:
        logger.warning("Agent unavailable: %s", e)
        error_text = _md(user_key_unavailable_message(str(e)))
        if placeholder:
            await placeholder.edit_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.exception("Unhandled error in handle_message: %s", e)
        error_text = _md("⚠️ An unexpected error occurred. Please try again.")
        if placeholder:
            await placeholder.edit_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(error_text, parse_mode=ParseMode.MARKDOWN_V2)
    finally:
        if typing_task:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass
