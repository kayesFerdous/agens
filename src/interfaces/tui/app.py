from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .commands import execute_command, parse_command
from .history import InputHistory
from .prefs import get_selected_model, set_selected_model
from .theme import ASSISTANT_CSS
from .widgets.chat_view import ChatView
from .widgets.command_palette import CommandPalette
from .widgets.header import AppHeader
from .widgets.horizontal_rule import HorizontalRule
from .widgets.inline_confirmation import ConfirmationRequest, InlineConfirmation
from .widgets.input_row import InputRow
from .widgets.no_api_keys import NoAPIKeysOnboarding
from .widgets.tool_block import ToolBlock
from .widgets.tool_group import ToolGroup
from interfaces.api_key_state import has_active_api_keys, user_key_unavailable_message


class AssistantTUI(App):
    CSS = ASSISTANT_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+k", "focus_input", "Focus input"),
        Binding("escape", "interrupt", "Interrupt"),
        Binding("enter", "no_key_select", "Select", priority=True, show=False),
        Binding("up", "history_prev", "Previous input", show=False),
        Binding("down", "history_next", "Next input", show=False),
    ]

    def __init__(self, agent: Any, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self._no_api_keys_at_startup = bool(getattr(agent, "no_api_keys_at_startup", False))
        self.session_id = str(uuid.uuid4())
        self._history = InputHistory(max_size=50)
        self._stream_task: asyncio.Task[None] | None = None
        self._current_generator: AsyncIterator[Any] | None = None
        self._current_block = None
        self._spinner = None
        self._current_tool_group: ToolGroup | None = None
        self._pending_tool_blocks: dict[str, ToolBlock] = {}
        self._token_count = 0
        self._selected_model: str | None = get_selected_model()  # restored from prefs
        self.model_name = self._detect_model_name()
        self._awaiting_confirmation = False
        self._waiting_for_api_key = self._no_api_keys_at_startup
        self._active_no_api_key_prompt: NoAPIKeysOnboarding | None = None
        self._api_key_modal_open = False
        self._confirmation_lock = asyncio.Lock()
        self._pending_confirmation_response: str | None = None
        self._active_confirmation: InlineConfirmation | None = None
        self._suppress_confirmation_tokens = False
        self._stop_requested = False

    def compose(self) -> ComposeResult:
        yield AppHeader(id="app-header")
        yield ChatView(id="chat")
        yield HorizontalRule()
        yield CommandPalette(id="command-palette")
        yield InputRow(id="input-row")
        yield Static("", id="model-bar")

    async def on_mount(self) -> None:
        await self._ensure_repo_session()
        from .widgets.model_select import get_model_label
        self.query_one(AppHeader).update_model(get_model_label(self.model_name))
        self._update_model_bar()
        if self._waiting_for_api_key:
            await self._mount_no_api_keys_onboarding()
        else:
            self.query_one(InputRow).focus_input()
            await self._mount_welcome()

    async def _mount_no_api_keys_onboarding(self) -> None:
        input_row = self.query_one(InputRow)
        input_row.set_locked(True)
        self._active_no_api_key_prompt = await self.query_one(ChatView).add_no_api_keys_onboarding()
        self._active_no_api_key_prompt.focus()

    def on_no_api_keys_onboarding_add_key(
        self, _: NoAPIKeysOnboarding.AddKey
    ) -> None:
        self.show_api_key_add()

    async def on_no_api_keys_onboarding_dismiss(
        self, _: NoAPIKeysOnboarding.Dismiss
    ) -> None:
        prompt = self._active_no_api_key_prompt
        self._active_no_api_key_prompt = None
        if prompt is not None:
            await prompt.remove()
        self.query_one(InputRow).set_locked(False)
        await self.query_one(ChatView).add_system(
            "Chat messages are disabled until you add an active API key. You can still use commands like [bold]/addkey[/bold], [bold]/keys[/bold], or [bold]/quit[/bold]."
        )
        self.query_one(InputRow).focus_input()

    def on_key(self, event: events.Key) -> None:
        if self._active_no_api_key_prompt is not None and not self._api_key_modal_open:
            if self._active_no_api_key_prompt.handle_prompt_key(event):
                return

        if self._awaiting_confirmation:
            if self._route_confirmation_key(event):
                return

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
        if self._is_streaming or self._awaiting_confirmation:
            return

        if parse_command(text):
            self._history.add(text)
            asyncio.create_task(execute_command(text, self))
            return

        if self._waiting_for_api_key:
            asyncio.create_task(
                self.query_one(ChatView).add_system(
                    "Chat messages are disabled until you add an active API key. Type [bold]/addkey[/bold] to add one."
                )
            )
            return

        self._history.add(text)

        asyncio.create_task(self._run_turn(text))

    async def _run_turn(self, text: str, *, render_user: bool = True) -> None:
        self._current_tool_group = None
        self._pending_tool_blocks = {}
        self._current_block = None
        chat = self.query_one(ChatView)

        if render_user:
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
                    was_near_bottom = chat.is_near_bottom()
                    if self._current_block is None:
                        if self._spinner is not None:
                            await self._spinner.stop()
                            self._spinner = None
                        self._current_block = await chat.add_assistant()
                    self._current_block.append_chunk(chunk)
                    self._token_count += len(chunk.split())
                    header.update_tokens(self._token_count)
                    chat.maybe_scroll_end(was_near_bottom=was_near_bottom)

        except asyncio.CancelledError:
            if self._stop_requested:
                await self._render_stream_stopped()
            elif self._current_block is not None:
                self._current_block.mark_interrupted()

        except Exception as exc:
            await self._add_assistant_error(user_key_unavailable_message(str(exc)))

        finally:
            self._current_generator = None
            if self._spinner is not None:
                await self._spinner.stop()
                self._spinner = None

            self._current_block = None
            self._pending_tool_blocks = {}
            pending_confirmation_response = self._pending_confirmation_response
            self._pending_confirmation_response = None
            self._stream_task = None
            self._stop_requested = False
            chat.maybe_scroll_end()
            if pending_confirmation_response is not None:
                await self._run_turn(pending_confirmation_response, render_user=False)
            elif not self._awaiting_confirmation:
                self.query_one(InputRow).focus_input()

    async def show_tool_call(self, tool_name: str, args: dict | str = "") -> ToolBlock:
        """Call this when a tool starts executing."""
        chat = self.query_one(ChatView)
        was_near_bottom = chat.is_near_bottom()
        if self._current_tool_group is None:
            self._current_tool_group = ToolGroup()
            await chat.mount(self._current_tool_group)
        block = await self._current_tool_group.add_tool(tool_name, args)
        chat.maybe_scroll_end(was_near_bottom=was_near_bottom)
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
            if self._suppress_confirmation_tokens:
                return ""
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
            await self._add_assistant_error(user_key_unavailable_message(str(error)))
        elif kind == "confirmation_required":
            await self._show_confirmation_event(event, kind)
        elif kind == "sudo_auth_required":
            await self._show_confirmation_event(event, kind)
        elif kind == "confirmation_result":
            await self._render_confirmation_result(event)
        elif kind == "done":
            self._suppress_confirmation_tokens = False
            usage = self._event_value(event, "usage")
            usage_total = getattr(usage, "total_tokens", None)
            if usage_total is not None:
                self._token_count = usage_total
                self.query_one(AppHeader).update_tokens(self._token_count)

        return ""

    async def _add_assistant_error(self, message: str) -> None:
        if self._spinner is not None:
            await self._spinner.stop()
            self._spinner = None
        block = await self.query_one(ChatView).add_assistant()
        block.append_chunk(message)

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

    async def _render_confirmation_result(self, event: Any) -> None:
        if self._spinner is not None:
            await self._spinner.stop()
            self._spinner = None

        result = self._event_value(event, "result", None)
        error = self._event_value(event, "error", None)
        message = self._event_value(event, "message", None)

        self._suppress_confirmation_tokens = True
        chat = self.query_one(ChatView)

        if isinstance(result, dict):
            command, output, exit_code, failed = self._format_command_result(result)
            await chat.add_command_result(
                command=command,
                output=output,
                exit_code=exit_code,
                failed=failed,
            )
        elif error:
            tool_name = str(self._event_value(event, "tool", None) or "command")
            await chat.add_command_result(
                command=tool_name,
                output=str(error),
                exit_code="error",
                failed=True,
            )
        elif message:
            await chat.add_system(str(message))

    def _format_command_result(self, result: dict[str, Any]) -> tuple[str, str, object, bool]:
        command = str(result.get("command") or "command")
        status = str(result.get("status") or "")
        exit_code = result.get("exit_code", "n/a")
        stdout = str(result.get("stdout") or "").strip()
        stderr = str(result.get("stderr") or "").strip()
        error = str(result.get("error") or "").strip()

        output = stdout or stderr or error or "No output."
        failed = status == "error" or bool(error)
        return command, output, exit_code, failed

    async def _show_confirmation_event(self, event: Any, kind: str) -> None:
        preview = self._event_value(event, "confirmation_preview", "") or ""
        warning = (
            self._event_value(event, "confirmation_reason", None)
            or "This can modify system-level files or configuration."
        )
        if kind == "sudo_auth_required":
            warning = "Sudo authorization is required before this command can continue."

        async with self._confirmation_lock:
            if self._pending_confirmation_response is not None:
                return

            input_row = self.query_one(InputRow)
            request = ConfirmationRequest(
                title="Sudo Privileges Required",
                warning=warning,
                command=preview,
            )

            self._awaiting_confirmation = True
            input_row.set_locked(True)
            try:
                confirmed = await self._await_inline_confirmation(request)
            except Exception as exc:
                confirmed = False
                await self.query_one(ChatView).add_system(
                    f"[red]Confirmation error:[/red] {exc}. Command was cancelled."
                )
            finally:
                self._awaiting_confirmation = False
                input_row.set_locked(False)

            self._pending_confirmation_response = "Y" if confirmed else "N"

    async def _await_inline_confirmation(self, request: ConfirmationRequest) -> bool:
        confirmation = await self.query_one(ChatView).add_confirmation(request)
        self._active_confirmation = confirmation
        try:
            return await confirmation.wait()
        except asyncio.CancelledError:
            confirmation.resolve(False)
            raise
        finally:
            if self._active_confirmation is confirmation:
                self._active_confirmation = None

    def _route_confirmation_key(self, event: events.Key) -> bool:
        key = event.key.lower()
        if key in {"up", "down", "pageup", "pagedown", "home", "end"}:
            chat = self.query_one(ChatView)
            if key == "up":
                chat.scroll_up(animate=False)
            elif key == "down":
                chat.scroll_down(animate=False)
            elif key == "pageup":
                chat.scroll_page_up(animate=False)
            elif key == "pagedown":
                chat.scroll_page_down(animate=False)
            elif key == "home":
                chat.scroll_home(animate=False)
            elif key == "end":
                chat.scroll_end(animate=False)
            event.stop()
            event.prevent_default()
            return True

        if self._active_confirmation is not None:
            return self._active_confirmation.handle_key(event)
        return False

    def action_interrupt(self) -> None:
        if self._awaiting_confirmation and self._active_confirmation is not None:
            self._active_confirmation.resolve(False)
            return
        if self._stream_task and not self._stream_task.done():
            asyncio.create_task(self._stop_active_stream())

    async def _stop_active_stream(self) -> None:
        task = self._stream_task
        if task is None or task.done():
            return

        self._stop_requested = True
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _render_stream_stopped(self) -> None:
        chat = self.query_one(ChatView)
        if self._spinner is not None:
            await self._spinner.stop()
            self._spinner = None

        if self._current_block is None:
            self._current_block = await chat.add_assistant()

        prefix = "\n\n" if getattr(self._current_block, "content", "") else ""
        self._current_block.append_chunk(f"{prefix}*[stopped]*")
        chat.maybe_scroll_end()

    def action_clear_chat(self) -> None:
        if self._awaiting_confirmation or self._active_no_api_key_prompt is not None:
            return
        asyncio.create_task(self._do_clear())

    async def _do_clear(self) -> None:
        chat = self.query_one(ChatView)
        await chat.clear_all()
        await chat.add_system("Chat cleared. Type [bold]?[/bold] for help.")
        self._token_count = 0
        self.query_one(AppHeader).update_tokens(0)

    def action_focus_input(self) -> None:
        if self._awaiting_confirmation or self._active_no_api_key_prompt is not None:
            return
        self.query_one(InputRow).focus_input()

    def _route_no_api_key_prompt_action(self, key: str) -> bool:
        if self._active_no_api_key_prompt is None or self._api_key_modal_open:
            return False

        class PromptKey:
            def __init__(self, key: str) -> None:
                self.key = key

            def stop(self) -> None:
                pass

            def prevent_default(self) -> None:
                pass

        self._active_no_api_key_prompt.handle_prompt_key(PromptKey(key))  # type: ignore[arg-type]
        return True

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "no_key_select":
            return self._active_no_api_key_prompt is not None and not self._api_key_modal_open
        return True

    def action_no_key_select(self) -> None:
        self._route_no_api_key_prompt_action("enter")

    def action_history_prev(self) -> None:
        if self._route_no_api_key_prompt_action("up"):
            return
        if self._awaiting_confirmation or self._waiting_for_api_key:
            return
        previous = self._history.prev()
        if previous is not None:
            input_row = self.query_one(InputRow)
            input_row.query_one("#main-input").value = previous

    def action_history_next(self) -> None:
        if self._route_no_api_key_prompt_action("down"):
            return
        if self._awaiting_confirmation or self._waiting_for_api_key:
            return
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

            return self.agent.chat(
                text,
                self.session_id,
                Channel.TUI,
                model=self._selected_model,
            )
        return self.agent.chat(text)

    def show_model_selector(self) -> None:
        """Push the model selection modal; result is applied via callback."""
        from .widgets.model_select import ModelSelectScreen, get_model_label

        def _on_selected(selected: str | None) -> None:
            if selected is None:
                return  # user cancelled
            self._selected_model = selected
            set_selected_model(selected)  # persist across restarts
            label = get_model_label(selected)
            self.query_one(AppHeader).update_model(label)
            self._update_model_bar()
            asyncio.create_task(
                self.query_one(ChatView).add_system(
                    f"Model set to [bold]{label}[/bold]. All future messages will use this model."
                )
            )

        self.push_screen(ModelSelectScreen(current_model=self._selected_model), callback=_on_selected)

    def show_api_key_list(self) -> None:
        """Push the API key list modal."""
        from .widgets.api_key_manage import APIKeyListScreen

        def _on_closed(_: None) -> None:
            asyncio.create_task(self._refresh_api_key_gate())

        self.push_screen(APIKeyListScreen(), callback=_on_closed)

    def show_api_key_add(self) -> None:
        """Push the add-API-key modal; shows a success message on completion."""
        from .widgets.api_key_manage import APIKeyAddScreen

        def _on_result(result: str | None) -> None:
            self._api_key_modal_open = False
            if result is None:
                asyncio.create_task(self._refresh_api_key_gate())
                return
            asyncio.create_task(
                self._handle_api_key_added(result)
            )

        self._api_key_modal_open = True
        self.push_screen(APIKeyAddScreen(), callback=_on_result)

    async def _handle_api_key_added(self, result: str) -> None:
        await self.query_one(ChatView).add_system(result)
        await self._refresh_api_key_gate()

    async def _refresh_api_key_gate(self) -> None:
        if not self._waiting_for_api_key:
            return
        try:
            from db.database import async_session
            from db.repositories.api_key import APIKeyRepository

            async with async_session() as db:
                has_active_key = await has_active_api_keys(APIKeyRepository(db))
        except Exception as exc:
            await self.query_one(ChatView).add_system(
                f"[red]Could not check API keys:[/red] {exc}"
            )
            return

        if not has_active_key:
            if self._active_no_api_key_prompt is not None:
                self.query_one(InputRow).set_locked(True)
                self._active_no_api_key_prompt.focus()
            return

        self._waiting_for_api_key = False
        self._no_api_keys_at_startup = False
        prompt = self._active_no_api_key_prompt
        self._active_no_api_key_prompt = None
        if prompt is not None:
            await prompt.remove()
        input_row = self.query_one(InputRow)
        input_row.set_locked(False)
        await self.query_one(ChatView).add_system(
            "API key ready. Chat input is now enabled."
        )
        input_row.focus_input()

    def _update_model_bar(self) -> None:
        """Refresh the one-line status bar below the input with the active model."""
        from .widgets.model_select import get_model_label
        try:
            bar = self.query_one("#model-bar", Static)
            if self._selected_model:
                label = get_model_label(self._selected_model)
                bar.update(f"  [dim]model:[/dim] [#cc785c]{label}[/#cc785c]  [dim]· /models to change[/dim]")
            else:
                label = get_model_label(self.model_name)
                bar.update(f"  [dim]model:[/dim] {label}  [dim]· /models to change[/dim]")
        except Exception:
            pass

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
