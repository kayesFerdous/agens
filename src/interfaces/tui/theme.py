from __future__ import annotations

THEME = {
    "background": "#0d0d0d",
    "surface": "#1a1a1a",
    "panel": "#141414",
    "header_bg": "#1a1a2e",
    "accent": "#cc785c",
    "accent_alt": "#4a9eff",
    "text_primary": "#e8e6e3",
    "text_muted": "#6b6b6b",
    "border_color": "#2a2a2a",
    "user_bubble_bg": "#1e2030",
    "success": "#4caf50",
    "error": "#f44336",
}

DEFAULT_CSS = f"""
Screen {{
    background: {THEME["background"]};
    color: {THEME["text_primary"]};
}}

#app-header {{
    dock: top;
    height: 1;
    background: {THEME["header_bg"]};
    color: {THEME["text_primary"]};
    layout: horizontal;
    padding: 0 1;
}}

#header-title, #header-model, #header-tokens {{
    width: 1fr;
    height: 1;
}}

#header-title {{
    color: {THEME["accent"]};
    text-style: bold;
}}

#header-model {{
    content-align: center middle;
    color: {THEME["text_muted"]};
}}

#header-tokens {{
    content-align: right middle;
    color: {THEME["text_muted"]};
}}

ChatView {{
    background: {THEME["background"]};
    padding: 1 2;
}}

.user-message {{
    align-horizontal: right;
    width: 88%;
    margin: 1 0;
}}

.user-box {{
    background: {THEME["user_bubble_bg"]};
    border: round {THEME["accent_alt"]};
    color: {THEME["text_primary"]};
    padding: 0 1;
}}

.assistant-message {{
    width: 100%;
    margin: 1 0;
}}

.message-label {{
    height: 1;
    color: {THEME["accent"]};
    text-style: bold;
}}

.user-label {{
    color: {THEME["accent_alt"]};
    content-align: right middle;
}}

.assistant-rule {{
    height: 1;
    color: {THEME["border_color"]};
}}

.assistant-markdown {{
    background: {THEME["background"]};
    color: {THEME["text_primary"]};
}}

.system-message {{
    margin: 1 0;
    color: {THEME["text_muted"]};
    text-style: italic;
}}

StreamingSpinner {{
    height: 1;
    margin: 1 0;
    color: {THEME["accent"]};
}}

#input-panel {{
    dock: bottom;
    height: auto;
    max-height: 10;
    background: {THEME["panel"]};
    border-top: solid {THEME["border_color"]};
    padding: 0 1;
}}

PromptInput {{
    height: 3;
    max-height: 8;
    background: {THEME["surface"]};
    color: {THEME["text_primary"]};
    border: round {THEME["border_color"]};
    padding: 0 1;
}}

PromptInput:focus {{
    border: round {THEME["accent"]};
}}

#footer-hints {{
    height: 1;
    color: {THEME["text_muted"]};
}}
"""
