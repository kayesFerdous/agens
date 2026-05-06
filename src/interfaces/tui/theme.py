from __future__ import annotations

ASSISTANT_CSS = """
Screen {
    background: #0d0d0d;
    color: #d4d4d4;
    layout: vertical;
}

AppHeader {
    height: 1;
    background: #111827;
    layout: horizontal;
    padding: 0 1;
}

AppHeader .header-title {
    color: #cc785c;
    text-style: bold;
    width: auto;
}

AppHeader .header-model {
    color: #4b5563;
    width: 1fr;
    content-align: center middle;
}

AppHeader .header-tokens {
    color: #4b5563;
    width: auto;
}

ChatView {
    height: 1fr;
    min-height: 10;
    background: #0d0d0d;
    border: none !important;
    outline: none !important;
    padding: 1 2;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-size: 1 1;
    scrollbar-color: #1f1f1f #0d0d0d;
}

ScrollView {
    border: none !important;
    outline: none !important;
}

UserBlock {
    height: auto;
    width: 100%;
    background: #1a1a1a;
    border: none;
    padding: 0 2;
    margin: 0 0 1 0;
}

AssistantBlock {
    height: auto;
    min-height: 3;
    width: 100%;
    background: transparent;
    border: none;
    padding: 0 0 1 0;
    margin: 0;
}

AssistantBlock Markdown {
    height: auto;
    min-height: 1;
    width: 100%;
    background: transparent;
    padding: 0;
    margin: 0;
}

Markdown {
    height: auto;
    min-height: 1;
    width: 100%;
}

SystemLine {
    height: auto;
    min-height: 1;
    width: 100%;
    background: transparent;
    border: none;
    color: #4b5563;
    text-style: italic;
    padding: 0 0 1 0;
    margin: 0;
}

LiveSpinner {
    height: 1;
    width: 100%;
    background: transparent;
    border: none;
    margin: 0 0 1 0;
}

HorizontalRule {
    display: none;
}

InputRow {
    height: auto;
    min-height: 3;
    background: #0d0d0d;
    layout: vertical;
    padding: 0;
    margin: 0 0 1 0;
    border: none;
}

InputRow .input-top-rule {
    height: 1;
    color: #2a2a2a;
    background: #0d0d0d;
    padding: 0;
}

InputRow .input-bottom-rule {
    height: 1;
    color: #2a2a2a;
    background: #0d0d0d;
    padding: 0;
}

InputRow .input-line {
    height: 1;
    min-height: 1;
    layout: horizontal;
    background: #0d0d0d;
    padding: 0 2;
}

InputRow .prompt-char {
    width: 3;
    color: #cc785c;
    text-style: bold;
    background: transparent;
    padding: 0;
}

InputRow Input {
    height: 1;
    min-height: 1;
    width: 1fr;
    background: transparent;
    border: none;
    color: #d4d4d4;
    padding: 0;
}

InputRow Input:focus {
    border: none;
    background: transparent;
}

InputRow Horizontal {
    height: 1;
    min-height: 1;
    background: #0d0d0d;
    padding: 0 2;
}

Tabs {
    display: none;
    height: 0;
}

TabPane {
    display: none;
}

TabbedContent {
    display: none;
}

Footer {
    display: none;
}

/* ── Model status bar (below InputRow) ─────────────────────────────── */
#model-bar {
    height: 1;
    width: 100%;
    background: #0d0d0d;
    color: #4b5563;
    padding: 0 1;
}

/* ── Model selection modal ─────────────────────────────────────────── */
ModelSelectScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.80);
}

#model-panel {
    width: 68;
    height: auto;
    max-height: 34;
    background: #111111;
    border: solid #2a2a2a;
}

#model-title-bar {
    height: auto;
    background: #0d0d0d;
    border-bottom: solid #2a2a2a;
    padding: 0 2;
}

#model-title {
    height: 1;
    width: 100%;
    color: #cc785c;
    text-style: bold;
    padding: 0;
}

#model-search {
    height: 1;
    width: 100%;
    background: #1a1a1a;
    border: solid #2a2a2a;
    color: #d4d4d4;
    padding: 0 2;
    margin: 1 1;
}

#model-search:focus {
    border: solid #cc785c;
}

#model-list {
    height: auto;
    max-height: 22;
    width: 100%;
    background: #111111;
    border: none;
    color: #d4d4d4;
    padding: 0;
    overflow-y: auto;
    scrollbar-size: 1 1;
    scrollbar-color: #2a2a2a #111111;
}

#model-list > .option-list--option {
    padding: 0 2;
    color: #d4d4d4;
}

#model-list > .option-list--option-highlighted {
    background: #cc785c;
    color: #ffffff;
    text-style: bold;
}

#model-list > .option-list--option-disabled {
    color: #4b5563;
    text-style: bold;
    background: transparent;
    padding: 0 2;
}

#model-footer {
    height: 1;
    width: 100%;
    color: #4b5563;
    background: #0d0d0d;
    border-top: solid #2a2a2a;
    padding: 0;
}
"""

DEFAULT_CSS = ASSISTANT_CSS
