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
    padding: 1 1;
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
    margin: 0;
    margin-top: 1;
}

AssistantBlock {
    height: auto;
    min-height: 1;
    width: 100%;
    background: transparent;
    border: none;
    padding: 0 2;
    margin: 0;
    margin-top: 1;
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
    padding: 0 2;
    margin: 0;
    margin-top: 1;
}

LiveSpinner {
    height: 1;
    width: 100%;
    background: transparent;
    border: none;
    margin: 0;
    margin-top: 1;
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

InputRow.locked {
    opacity: 60%;
}

InputRow.locked Input {
    color: #4b5563;
}

InputRow Horizontal {
    height: 1;
    min-height: 1;
    background: #0d0d0d;
    padding: 0 2;
}

/* ── Inline confirmation ─────────────────────────────────────────── */
InlineConfirmation {
    height: auto;
    width: 100%;
    background: transparent;
    padding: 0 0 0 2;
    margin: 0;
}

InlineConfirmation .confirm-box {
    width: 72;
    max-width: 96%;
    height: auto;
    background: #101010;
    border-left: solid #cc785c;
    border-top: none;
    border-right: none;
    border-bottom: none;
    padding: 0 1;
}

InlineConfirmation .confirm-title {
    height: 1;
    width: 100%;
    color: #9a9a9a;
    text-style: bold;
    padding: 0;
}

InlineConfirmation .confirm-command {
    height: 1;
    width: 100%;
    color: #d7d7d7;
    background: #0b0b0b;
    padding: 0 1;
    margin: 0;
}

InlineConfirmation .confirm-warning {
    height: auto;
    min-height: 1;
    width: 100%;
    background: transparent;
    color: #777777;
    padding: 0;
}

CommandResultBlock {
    height: auto;
    width: 100%;
    background: transparent;
    padding: 0;
    margin: 0;
    margin-top: 1;
}

CommandResultBlock .command-result-box {
    height: auto;
    width: 100%;
    background: transparent;
    padding: 0;
    margin: 0;
}

CommandResultBlock .command-result-title {
    height: 1;
    color: #d4d4d4;
    text-style: bold;
    padding: 0;
}

CommandResultBlock .command-result-command {
    height: 1;
    color: #d7d7d7;
    background: #0b0b0b;
    padding: 0 1;
    margin: 0;
}

CommandResultBlock .command-result-exit {
    height: 1;
    color: #777777;
    padding: 0;
    margin: 0;
}

CommandResultBlock .command-result-output {
    height: auto;
    width: 100%;
    color: #f1f1f1;
    background: #0b0b0b;
    padding: 0 1;
    margin: 0;
}

InlineConfirmation .confirm-actions {
    height: 1;
    width: 100%;
    align: left middle;
    background: transparent;
    padding: 0;
    margin: 0;
}

InlineConfirmation .confirm-actions Button {
    height: 1;
    min-width: 7;
    margin: 0 1 0 0;
    padding: 0 1;
    background: #1a1a1a;
    border: none;
    color: #bdbdbd;
}

InlineConfirmation .confirm-actions Button.selected {
    background: #cc785c;
    color: #ffffff;
    text-style: bold;
}

InlineConfirmation .confirm-yes.selected {
    background: #8a4f3d;
}

InlineConfirmation .confirm-no.selected {
    background: #cc785c;
}

InlineConfirmation.resolved .confirm-title {
    color: #777777;
}

NoAPIKeysOnboarding {
    height: auto;
    width: 100%;
    background: transparent;
    padding: 0 0 0 2;
    margin: 1 0 0 0;
}

NoAPIKeysOnboarding .no-keys-box {
    width: 74;
    max-width: 96%;
    height: auto;
    background: #101010;
    border-left: solid #cc785c;
    padding: 0 1;
}

NoAPIKeysOnboarding .no-keys-title {
    height: 1;
    color: #f4f4f5;
    text-style: bold;
}

NoAPIKeysOnboarding .no-keys-copy {
    height: auto;
    min-height: 1;
    color: #9a9a9a;
}

NoAPIKeysOnboarding .no-keys-option {
    height: 1;
    width: 100%;
    color: #d4d4d4;
    background: transparent;
    margin: 1 0 0 0;
    padding: 0;
}

NoAPIKeysOnboarding .no-keys-option.selected {
    color: #f4f4f5;
    text-style: bold;
}

NoAPIKeysOnboarding .no-keys-shortcuts {
    height: 1;
    color: #4b5563;
    margin: 1 0 0 0;
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

/* ── API Key list modal ───────────────────────────────────────────── */
APIKeyListScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.80);
}

#apikey-panel {
    width: 96;
    height: auto;
    max-height: 34;
    background: #111111;
    border: solid #2a2a2a;
}

#apikey-title-bar {
    height: auto;
    background: #0d0d0d;
    border-bottom: solid #2a2a2a;
    padding: 0 2;
}

#apikey-title {
    height: 1;
    width: 100%;
    color: #cc785c;
    text-style: bold;
    padding: 0;
}

#apikey-footer {
    height: 2;
    min-height: 2;
    width: 100%;
    background: #0d0d0d;
    border-top: solid #2a2a2a;
    padding: 0;
}

#apikey-header-row {
    height: 1;
    width: 100%;
    background: #111111;
    padding: 0 2;
}

#apikey-list {
    height: auto;
    max-height: 18;
    width: 100%;
    background: #111111;
    border: none;
    color: #d4d4d4;
    padding: 0;
    overflow-y: auto;
    scrollbar-size: 1 1;
    scrollbar-color: #2a2a2a #111111;
}

#apikey-list > .option-list--option {
    padding: 0 2;
    color: #d4d4d4;
}

#apikey-list > .option-list--option-highlighted {
    background: #1e293b;
    color: #ffffff;
}

#apikey-summary {
    height: auto;
    min-height: 1;
    width: 100%;
    background: #111111;
    padding: 0 2;
    color: #4b5563;
}

/* ── Add API Key modal ────────────────────────────────────────────── */
APIKeyAddScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.80);
}

#addkey-panel {
    width: 60;
    height: auto;
    max-height: 28;
    background: #111111;
    border: solid #2a2a2a;
}

#addkey-title-bar {
    height: auto;
    background: #0d0d0d;
    border-bottom: solid #2a2a2a;
    padding: 0 2;
}

#addkey-title {
    height: 1;
    width: 100%;
    color: #cc785c;
    text-style: bold;
    padding: 0;
}

#addkey-form {
    padding: 1 2;
    height: auto;
}

#addkey-form .field-label {
    height: 1;
    margin: 1 0 0 0;
    padding: 0;
    background: transparent;
}

#addkey-form .field-hint {
    height: 1;
    margin: 0;
    padding: 0;
    color: #4b5563;
    background: transparent;
}

#addkey-form Input {
    height: 1;
    width: 100%;
    background: #1a1a1a;
    border: solid #2a2a2a;
    color: #d4d4d4;
    padding: 0 1;
    margin: 0 0 0 0;
}

#addkey-form Input:focus {
    border: solid #cc785c;
}

#addkey-status {
    height: auto;
    min-height: 1;
    padding: 0 2;
    background: transparent;
}

#addkey-actions {
    height: 3;
    padding: 0 2;
    align: right middle;
}

#addkey-actions Button {
    margin: 0 1;
    min-width: 12;
}

#addkey-save {
    background: #cc785c;
    color: #ffffff;
    text-style: bold;
    border: none;
}

#addkey-cancel {
    background: #2a2a2a;
    color: #d4d4d4;
    border: none;
}

#addkey-footer {
    height: 1;
    width: 100%;
    color: #4b5563;
    background: #0d0d0d;
    border-top: solid #2a2a2a;
    padding: 0;
}
"""

DEFAULT_CSS = ASSISTANT_CSS
