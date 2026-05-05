from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import AsyncIterator
from typing import Any
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static, TextArea
from .commands import handle_command, is_command
from .history import InputHistory
from .theme import DEFAULT_CSS
from .widgets import AssistantMessage, ChatView, StreamingSpinner, SystemMessage, UserMessage

class PromptInput(TextArea):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__(); self.text = text

    async def on_key(self, event: events.Key) -> None:
        if event.key == "shift+enter":
            return
        if event.key == "enter":
            event.prevent_default(); event.stop()
            self.post_message(self.Submitted(self.text))

class AssistantTUI(App):
    CSS = DEFAULT_CSS
    BINDINGS = [
        Binding(k, a, show=False) for k, a in [("ctrl+c", "quit"), ("ctrl+q", "quit"),
        ("ctrl+l", "clear_chat"), ("escape", "cancel_stream"), ("ctrl+k", "focus_input"),
        ("pageup", "page_up"), ("pagedown", "page_down"), ("up", "history_prev"),
        ("down", "history_next")]
    ]
    def __init__(self, agent: Any) -> None:
        super().__init__()
        self.agent, self.history = agent, InputHistory(max_items=50)
        self.current_task: asyncio.Task[None] | None = None
        self.current_generator: AsyncIterator[Any] | None = None
        self.is_streaming, self.token_count = False, 0
        self.session_id = str(uuid.uuid4())
        self.model_name = self._detect_model_name()
    def compose(self) -> ComposeResult:
        with Horizontal(id="app-header"):
            yield Static("◆ Assistant", id="header-title"); yield Static(self.model_name, id="header-model")
            yield Static("tokens: 0", id="header-tokens")
        yield ChatView(id="chat")
        with Vertical(id="input-panel"):
            yield PromptInput("", id="prompt"); yield Static("? for help · /clear · /exit              tokens: 0", id="footer-hints")
    async def on_mount(self) -> None:
        await self._ensure_repo_session(); self.query_one(PromptInput).focus()
    async def on_prompt_input_submitted(self, message: PromptInput.Submitted) -> None:
        text = message.text.strip()
        if not text or self.is_streaming:
            return
        self.query_one(PromptInput).load_text("")
        if is_command(text): await handle_command(text, self)
        else: self.history.add(text); self.current_task = asyncio.create_task(self.send_message(text))
    async def send_message(self, text: str) -> None:
        chat, assistant, spinner = self.query_one(ChatView), AssistantMessage(), StreamingSpinner()
        await chat.mount_message(UserMessage(text)); await chat.mount_message(assistant)
        await chat.mount_message(spinner)
        self.is_streaming = True
        try:
            self.current_generator = self._chat_stream(text)
            async for event in self.current_generator:
                await self._handle_stream_event(event, assistant)
                chat.scroll_to_bottom()
        except asyncio.CancelledError:
            assistant.mark_interrupted()
        except Exception as exc:
            await self.add_system_message(f"◆ System\n\nError: `{type(exc).__name__}: {exc}`")
        finally:
            self.current_generator = None; self.is_streaming = False
            if spinner.is_mounted:
                await spinner.remove()
            self.current_task = None; chat.scroll_to_bottom()
            self.query_one(PromptInput).focus()
    async def add_system_message(self, text: str) -> None:
        await self.query_one(ChatView).mount_message(SystemMessage(text))
    async def clear_chat(self) -> None:
        await self.query_one(ChatView).clear_messages()
    async def action_clear_chat(self) -> None:
        await self.clear_chat(); await self.add_system_message("◆ System\n\nChat cleared.")
    def action_focus_input(self) -> None: self.query_one(PromptInput).focus()
    def action_page_up(self) -> None: self.query_one(ChatView).scroll_page_up(animate=False)
    def action_page_down(self) -> None: self.query_one(ChatView).scroll_page_down(animate=False)
    async def action_cancel_stream(self) -> None:
        if self.current_generator is not None and hasattr(self.current_generator, "aclose"):
            await self.current_generator.aclose()
        if self.current_task is not None:
            self.current_task.cancel()
    def action_history_prev(self) -> None:
        prompt = self.query_one(PromptInput)
        self._load_history(self.history.prev() if not prompt.text.strip() else None)
    def action_history_next(self) -> None:
        prompt = self.query_one(PromptInput)
        if prompt.text.strip() and not self.history.has_cursor:
            return
        self._load_history(self.history.next())
    def _load_history(self, value: str | None) -> None:
        if value is not None: self.query_one(PromptInput).load_text(value)
    async def _handle_stream_event(self, event: Any, assistant: AssistantMessage) -> None:
        kind = getattr(event, "type", "")
        if kind == "token" and getattr(event, "content", None):
            assistant.append_text(event.content)
        elif kind == "status" and getattr(event, "message", None):
            await self.add_system_message(f"◆ System\n\n{event.message}")
        elif kind == "error":
            await self.add_system_message(f"◆ System\n\nError: `{getattr(event, 'error', 'Unknown error')}`")
        elif kind in {"confirmation_required", "sudo_auth_required"}:
            await self._show_confirmation_event(event, kind)
        elif kind == "done" and getattr(event, "usage", None) is not None:
            self.token_count = getattr(event.usage, "total_tokens", self.token_count) or self.token_count
            self._update_token_labels()
    async def _show_confirmation_event(self, event: Any, kind: str) -> None:
        preview = getattr(event, "confirmation_preview", "") or ""
        if kind == "sudo_auth_required":
            await self.add_system_message(f"◆ System\n\nSudo authorization required for `{preview}`."); return
        reason = getattr(event, "confirmation_reason", "") or "Confirmation required."
        await self.add_system_message(f"◆ System\n\n{reason}\n\n`{preview}`\n\nReply `YES` to proceed.")
    def _chat_stream(self, text: str) -> AsyncIterator[Any]:
        params = inspect.signature(self.agent.chat).parameters
        if "source" in params:
            return self.agent.chat(text, source="tui")
        if "channel" in params:
            from agent.agent import Channel
            return self.agent.chat(text, self.session_id, Channel.TUI)
        return self.agent.chat(text)
    async def _ensure_repo_session(self) -> None:
        if "session_id" not in inspect.signature(self.agent.chat).parameters: return
        try:
            from db import repository as session_repo
            from db.database import async_session
            async with async_session() as db:
                self.session_id = (await session_repo.insert_session(db, title="TUI Session")).id
        except Exception:
            await self.add_system_message("◆ System\n\nCould not create a database session. Using an ephemeral TUI session.")
    def _detect_model_name(self) -> str:
        llm = getattr(self.agent, "_llm", None)
        return str(getattr(llm, "model_name", None) or getattr(self.agent, "model_name", "model"))
    def _update_token_labels(self) -> None:
        text = f"tokens: {self.token_count}"
        self.query_one("#header-tokens", Static).update(text)
        self.query_one("#footer-hints", Static).update(f"? for help · /clear · /exit              {text}")
