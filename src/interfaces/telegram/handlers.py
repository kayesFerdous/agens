import asyncio
import logging
import re
from html import escape as html_escape, unescape

import markdown
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes, Application

from agent.agent import Agent, Channel
from core.model_catalog import ALL_MODELS, get_model_label, resolve_model
from core.tool_groups import DEFAULT_TOOL_GROUPS
from db.database import async_session
from db import repository as session_repo
from db.models import APIKey, KeyStatus
from db.repositories.api_key import APIKeyRepository
from interfaces.api_key_state import (
    NO_API_KEYS_TELEGRAM_MESSAGE,
    has_any_api_keys,
    user_key_unavailable_message,
)
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
    model_label = get_model_label(model_name) if model_name else "the default model"
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
            f"*{_md('Current model:')}* `{_md(get_model_label(current_model))}`\n\n"
            f"{_md('Tap a model below to change it.')}"
        )
    return (
        f"*{_md('Current model:')}* `default`\n\n"
        f"{_md('Tap a model below to set one, or keep using the default model.')}"
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
                    "\n".join([
                        "*Model updated*",
                        "",
                        _md(f"Now using {get_model_label(resolved)}."),
                        _md("New chats will use this model."),
                    ]),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                return

    current_model = _current_model_for_user(update)
    await update.message.reply_text(  # type: ignore[union-attr]
        _render_model_prompt(current_model),
        reply_markup=_build_model_keyboard(current_model),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_model_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.data.startswith(MODEL_CALLBACK_PREFIX):
        return

    await query.answer()
    selection = query.data[len(MODEL_CALLBACK_PREFIX):]

    if selection == "close":
        await query.edit_message_text(
            "*Model picker closed*",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
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
        "\n".join([
            "*Model updated*",
            "",
            _md(f"Now using {get_model_label(resolved)}."),
            _md("New chats will use this model."),
        ]),
        reply_markup=_build_model_keyboard(resolved),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await query.answer(f"Model set to {get_model_label(resolved)}")


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
        f"{_md('Tap a tool group below to toggle it on or off.')}"
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
