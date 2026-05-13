from __future__ import annotations

from core.registry import ToolRegistry


DEFAULT_TOOL_GROUPS: dict[str, bool] = {
    "filesystem": True,
    "scheduling": True,
    "system": True,
    "web": True,
}

TOOL_GROUPS: dict[str, list[str]] = {
    "filesystem": ["file_read", "file_write", "file_edit", "list_directory", "find", "grep"],
    "scheduling": ["schedule_add", "schedule_delete", "schedule_list", "schedule_update"],
    "system": ["shell_command", "update_config"],
    "web": ["search_web"],
}


def normalize_tool_groups(tool_groups: dict[str, bool] | None) -> dict[str, bool]:
    """Return a complete, known-only tool-group preference map."""
    if tool_groups is None:
        return dict(DEFAULT_TOOL_GROUPS)

    return {
        group: bool(tool_groups.get(group, enabled))
        for group, enabled in DEFAULT_TOOL_GROUPS.items()
    }


def get_enabled_tool_names(tool_groups: dict[str, bool] | None) -> set[str]:
    enabled_groups = normalize_tool_groups(tool_groups)
    enabled_tools: set[str] = set()

    for group, enabled in enabled_groups.items():
        if enabled:
            enabled_tools.update(TOOL_GROUPS[group])

    return enabled_tools


def get_enabled_tool_schemas(
    registry: ToolRegistry,
    tool_groups: dict[str, bool] | None,
) -> list[dict]:
    """Return registered tool schemas whose groups are enabled."""
    enabled_tool_names = get_enabled_tool_names(tool_groups)
    return [
        schema
        for schema in registry.tool_schemas()
        if schema["name"] in enabled_tool_names
    ]
