from __future__ import annotations

from rich.segment import Segment
from rich.style import Style
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.widgets import SelectionList, Static
from textual.widgets.selection_list import Selection
from textual.widgets._option_list import OptionDoesNotExist
from textual.widgets._toggle_button import ToggleButton

from core.tool_groups import DEFAULT_TOOL_GROUPS, normalize_tool_groups
from interfaces.tui.prefs import set_tool_groups


TOOL_GROUP_OPTIONS: list[tuple[str, str, str]] = [
    ("filesystem", "Filesystem", "Read, search, write, and edit workspace files"),
    ("scheduling", "Scheduling", "Manage schedule events"),
    ("system", "System", "Run shell commands and update assistant config"),
    ("web", "Web", "Search the web and fetch full page content"),
]


class ThemedSelectionList(SelectionList[str]):
    BUTTON_LEFT = ToggleButton.BUTTON_LEFT
    BUTTON_INNER = "O"
    BUTTON_RIGHT = ToggleButton.BUTTON_RIGHT

    def render_line(self, y: int) -> Strip:
        line = super(SelectionList, self).render_line(y)

        _, scroll_y = self.scroll_offset
        selection_index = scroll_y + y
        try:
            selection = self.get_option_at_index(selection_index)
        except OptionDoesNotExist:
            return line

        component_style = "selection-list--button"
        if selection.value in self._selected:
            component_style += "-selected"
        if self.highlighted == selection_index:
            component_style += "-highlighted"

        underlying_style = next(iter(line)).style or self.rich_style
        assert underlying_style is not None

        button_style = self.get_component_rich_style(component_style)
        side_style = Style.from_color(button_style.bgcolor, underlying_style.bgcolor)
        side_style += Style(meta={"option": selection_index})
        button_style += Style(meta={"option": selection_index})

        return Strip(
            [
                Segment(self.BUTTON_LEFT, style=side_style),
                Segment(self.BUTTON_INNER, style=button_style),
                Segment(self.BUTTON_RIGHT, style=side_style),
                Segment(" ", style=underlying_style),
                *line,
            ]
        )


class ToolGroupSelectScreen(ModalScreen[dict[str, bool] | None]):
    """Modal checklist for enabling and disabling tool groups."""

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("ctrl+c", "close", "Close", priority=True),
        Binding("enter", "close", "Close", priority=True),
        Binding("t", "toggle_selection", "Toggle", show=False),
    ]

    def __init__(self, current_tool_groups: dict[str, bool]) -> None:
        super().__init__()
        self._current_tool_groups = normalize_tool_groups(current_tool_groups)
        self._dirty = False

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
                    "[bold]Tool groups[/bold]  [dim]t/space toggle · esc close[/dim]",
                    id="tool-groups-title",
                )
            yield ThemedSelectionList(*selections, id="tool-groups-list")
            yield Static(
                "  [dim]Disabled groups are omitted from the model prompt and tool schemas.[/dim]",
                id="tool-groups-footer",
            )

    def on_mount(self) -> None:
        self.query_one("#tool-groups-list", ThemedSelectionList).focus()

    def _current_selection(self) -> dict[str, bool]:
        selected = set(self.query_one("#tool-groups-list", ThemedSelectionList).selected)
        return {group: group in selected for group in DEFAULT_TOOL_GROUPS}

    def action_toggle_selection(self) -> None:
        self.query_one("#tool-groups-list", ThemedSelectionList).action_select()

    def on_selection_list_selection_toggled(self, _: SelectionList.SelectionToggled) -> None:
        self._dirty = True
        self._current_tool_groups = self._current_selection()
        set_tool_groups(self._current_tool_groups)

    def action_close(self) -> None:
        if self._dirty:
            self.dismiss(self._current_selection())
            return
        self.dismiss(None)
