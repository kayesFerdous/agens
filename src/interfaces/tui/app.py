from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding

from .commands import execute_command, parse_command
from .history import InputHistory
from .theme import ASSISTANT_CSS
from .widgets.chat_view import ChatView
from .widgets.command_palette import CommandPalette
from .widgets.header import AppHeader
from .widgets.horizontal_rule import HorizontalRule
from .widgets.input_row import InputRow
from .widgets.tool_block import ToolBlock
from .widgets.tool_group import ToolGroup


class AssistantTUI(App):
    CSS = ASSISTANT_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+k", "focus_input", "Focus input"),
        Binding("escape", "interrupt", "Interrupt"),
        Binding("up", "history_prev", "Previous input", show=False),
        Binding("down", "history_next", "Next input", show=False),
    ]

    def __init__(self, agent: Any, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.session_id = str(uuid.uuid4())
        self._history = InputHistory(max_size=50)
        self._stream_task: asyncio.Task[None] | None = None
        self._current_generator: AsyncIterator[Any] | None = None
        self._current_block = None
        self._spinner = None
        self._current_tool_group: ToolGroup | None = None
        self._pending_tool_blocks: dict[str, ToolBlock] = {}
        self._token_count = 0
        self.model_name = self._detect_model_name()

    def compose(self) -> ComposeResult:
        yield AppHeader(id="app-header")
        yield ChatView(id="chat")
        yield HorizontalRule()
        yield CommandPalette(id="command-palette")
        yield InputRow(id="input-row")

    async def on_mount(self) -> None:
        await self._ensure_repo_session()
        self.query_one(AppHeader).update_model(self.model_name)
        self.query_one(InputRow).focus_input()
        await self._mount_welcome()

    def on_key(self, event: events.Key) -> None:
        if event.key != "f12":
            return

        chat = self.query_one(ChatView)
        self.log(f"ChatView children: {list(chat.children)}")
        self.log(f"ChatView size: {chat.size}")
        self.log(f"ChatView region: {chat.region}")
        for child in chat.children:
            self.log(f"  child: {child} size={child.size} region={child.region}")

    async def _mount_welcome(self) -> None:
        await self.query_one(ChatView).add_system(
            "◆  Assistant ready. Type [bold]?[/bold] for help."
        )

    def handle_submit(self, text: str) -> None:
        if self._is_streaming:
            return

        self._history.add(text)

        if parse_command(text):
            asyncio.create_task(execute_command(text, self))
            return

        asyncio.create_task(self._run_turn(text))

    async def _run_turn(self, text: str) -> None:
        self._current_tool_group = None
        self._pending_tool_blocks = {}
        self._current_block = None
        chat = self.query_one(ChatView)

        await chat.add_user(text)
        self._spinner = await chat.add_spinner()

        self._stream_task = asyncio.create_task(self._stream(text))

    async def _stream(self, text: str) -> None:
        chat = self.query_one(ChatView)
        header = self.query_one(AppHeader)

        try:
            self._current_generator = self._chat_stream(text)
            async for event in self._current_generator:
                chunk = await self._handle_stream_event(event)
                if chunk:
                    if self._current_block is None:
                        if self._spinner is not None:
                            await self._spinner.stop()
                            self._spinner = None
                        self._current_block = await chat.add_assistant()
                    self._current_block.append_chunk(chunk)
                    self._token_count += len(chunk.split())
                    header.update_tokens(self._token_count)
                    chat.scroll_end(animate=False)

        except asyncio.CancelledError:
            if self._current_block is not None:
                self._current_block.append_chunk("\n\n*[interrupted]*")

        except Exception as exc:
            await chat.add_system(f"[red]Error:[/red] {exc}")

        finally:
            self._current_generator = None
            if self._spinner is not None:
                await self._spinner.stop()
                self._spinner = None

            self._current_block = None
            self._pending_tool_blocks = {}
            self._stream_task = None
            chat.scroll_end(animate=False)
            self.query_one(InputRow).focus_input()

    async def show_tool_call(self, tool_name: str, args: dict | str = "") -> ToolBlock:
        """Call this when a tool starts executing."""
        chat = self.query_one(ChatView)
        if self._current_tool_group is None:
            self._current_tool_group = ToolGroup()
            await chat.mount(self._current_tool_group)
        block = await self._current_tool_group.add_tool(tool_name, args)
        chat.scroll_end(animate=False)
        return block

    async def finish_tool_call(self, block: ToolBlock, output: str) -> None:
        """Call this when a tool finishes, passing its output."""
        block.set_output(output)
        if self._current_tool_group is not None and not self._pending_tool_blocks:
            self._current_tool_group.mark_done()

    async def _handle_stream_event(self, event: Any) -> str:
        if isinstance(event, str):
            return event

        kind = self._event_value(event, "type", "")
        if kind == "token":
            return str(self._event_value(event, "content", "") or "")

        if kind == "tool_start":
            tool_name = str(self._event_value(event, "tool", None) or "tool")
            arguments = self._event_value(event, "arguments", {}) or {}
            block = await self.show_tool_call(tool_name, arguments)
            self._pending_tool_blocks[tool_name] = block
            return ""

        if kind == "tool_end":
            tool_name = str(self._event_value(event, "tool", None) or "tool")
            block = self._pending_tool_blocks.pop(tool_name, None)
            if block is not None:
                await self.finish_tool_call(block, self._format_tool_output(event))
            return ""

        if kind == "status" and self._event_value(event, "message", None):
            await self.query_one(ChatView).add_system(str(self._event_value(event, "message")))
        elif kind == "error":
            error = self._event_value(event, "error", "Unknown error")
            await self.query_one(ChatView).add_system(f"[red]Error:[/red] {error}")
        elif kind in {"confirmation_required", "sudo_auth_required"}:
            await self._show_confirmation_event(event, kind)
        elif kind == "done" and self._event_value(event, "usage", None) is not None:
            usage = self._event_value(event, "usage")
            usage_total = getattr(usage, "total_tokens", None)
            if usage_total is not None:
                self._token_count = usage_total
                self.query_one(AppHeader).update_tokens(self._token_count)

        return ""

    def _event_value(self, event: Any, key: str, default: Any = None) -> Any:
        if isinstance(event, dict):
            return event.get(key, default)
        return getattr(event, key, default)

    def _format_tool_output(self, event: Any) -> str:
        error = self._event_value(event, "error", None)
        if error:
            return str(error)

        result = self._event_value(event, "result", "")
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, indent=2, ensure_ascii=False)
            except TypeError:
                return str(result)
        return str(result)

    async def _show_confirmation_event(self, event: Any, kind: str) -> None:
        preview = self._event_value(event, "confirmation_preview", "") or ""
        if kind == "sudo_auth_required":
            await self.query_one(ChatView).add_system(
                f"Sudo authorization required for `{preview}`."
            )
            return

        reason = self._event_value(event, "confirmation_reason", "") or "Confirmation required."
        await self.query_one(ChatView).add_system(
            f"{reason}\n\n`{preview}`\n\nReply `YES` to proceed."
        )

    def action_interrupt(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()

    def action_clear_chat(self) -> None:
        asyncio.create_task(self._do_clear())

    async def _do_clear(self) -> None:
        chat = self.query_one(ChatView)
        await chat.clear_all()
        await chat.add_system("Chat cleared. Type [bold]?[/bold] for help.")
        self._token_count = 0
        self.query_one(AppHeader).update_tokens(0)

    def action_focus_input(self) -> None:
        self.query_one(InputRow).focus_input()

    def action_history_prev(self) -> None:
        previous = self._history.prev()
        if previous is not None:
            input_row = self.query_one(InputRow)
            input_row.query_one("#main-input").value = previous

    def action_history_next(self) -> None:
        next_value = self._history.next()
        if next_value is not None:
            input_row = self.query_one(InputRow)
            input_row.query_one("#main-input").value = next_value

    def action_quit(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
        self.exit()

    def _chat_stream(self, text: str) -> AsyncIterator[Any]:
        params = inspect.signature(self.agent.chat).parameters
        if "source" in params:
            return self.agent.chat(text, source="tui")
        if "channel" in params:
            from agent.agent import Channel

            return self.agent.chat(text, self.session_id, Channel.TUI)
        return self.agent.chat(text)

    async def _ensure_repo_session(self) -> None:
        if "session_id" not in inspect.signature(self.agent.chat).parameters:
            return
        try:
            from db import repository as session_repo
            from db.database import async_session

            async with async_session() as db:
                self.session_id = (await session_repo.insert_session(db, title="TUI Session")).id
        except Exception:
            await self.query_one(ChatView).add_system(
                "Could not create a database session. Using an ephemeral TUI session."
            )

    def _detect_model_name(self) -> str:
        llm = getattr(self.agent, "_llm", None)
        return str(getattr(llm, "model_name", None) or getattr(self.agent, "model_name", "assistant"))

    @property
    def _is_streaming(self) -> bool:
        return self._stream_task is not None and not self._stream_task.done()

    @property
    def token_count(self) -> int:
        return self._token_count
