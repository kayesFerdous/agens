from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import SelectionList, Static
from textual.widgets.selection_list import Selection

from core.tool_groups import DEFAULT_TOOL_GROUPS, normalize_tool_groups


TOOL_GROUP_OPTIONS: list[tuple[str, str, str]] = [
    ("filesystem", "Filesystem", "Read, search, write, and edit workspace files"),
    ("scheduling", "Scheduling", "Manage schedule events"),
    ("system", "System", "Run shell commands and update assistant config"),
    ("web", "Web", "Search the web"),
]


class ToolGroupSelectScreen(ModalScreen[dict[str, bool] | None]):
    """Modal checklist for enabling and disabling tool groups."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True),
        Binding("enter", "save", "Save", priority=True),
    ]

    def __init__(self, current_tool_groups: dict[str, bool]) -> None:
        super().__init__()
        self._current_tool_groups = normalize_tool_groups(current_tool_groups)

    def compose(self) -> ComposeResult:
        selections = [
            Selection(
                f"[bold]{label}[/bold]  [dim]{description}[/dim]",
                group,
                self._current_tool_groups.get(group, DEFAULT_TOOL_GROUPS[group]),
            )
            for group, label, description in TOOL_GROUP_OPTIONS
        ]

        with Vertical(id="tool-groups-panel"):
            with Vertical(id="tool-groups-title-bar"):
                yield Static(
                    "[bold]Tool groups[/bold]  [dim]space toggle · enter save · esc cancel[/dim]",
                    id="tool-groups-title",
                )
            yield SelectionList(*selections, id="tool-groups-list")
            yield Static(
                "  [dim]Disabled groups are omitted from the model prompt and tool schemas.[/dim]",
                id="tool-groups-footer",
            )

    def on_mount(self) -> None:
        self.query_one("#tool-groups-list", SelectionList).focus()

    def action_save(self) -> None:
        selected = set(self.query_one("#tool-groups-list", SelectionList).selected)
        self.dismiss({group: group in selected for group in DEFAULT_TOOL_GROUPS})

    def action_cancel(self) -> None:
        self.dismiss(None)
