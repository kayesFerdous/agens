from __future__ import annotations

# ── Design System Tokens (reference) ──────────────────────────────────
# Background (chat body):     #0F0D0A   — warm near-black
# Surface (top bar, modals):  #1A1713   — slightly elevated warm dark
# Accent violet:              #7B6EAA   — primary interactive/selection
# Accent mid:                 #A99DD1   — secondary violet, hints/captions
# Warm copper:                #C97C4A   — tool execution, confirm ONLY
# Text primary:               #F5F0E8
# Text secondary:             #8C877E   (≈ rgba(245,240,232,0.55))
# Text muted:                 #56524C   (≈ rgba(245,240,232,0.30))
# Border:                     #28251F   (≈ rgba(245,240,232,0.10))
# ──────────────────────────────────────────────────────────────────────

ASSISTANT_CSS = """
Screen {
    background: #0F0D0A;
    color: #F5F0E8;
    layout: vertical;
    overflow: hidden hidden;
}

/* ── 1. TOP BAR — single fixed content row ─────────────────────────── */
AppHeader {
    height: 1;
    min-height: 1;
    background: #1A1713;
    layout: horizontal;
    padding: 0 2;
    border: none;
}

/* Left: app name */
AppHeader .header-title {
    color: #F5F0E8;
    text-style: bold;
    width: auto;
}

/* Left: session id — muted, after app name */
AppHeader .header-session {
    color: #56524C;
    width: auto;
}

/* Spacer pushes right zone to the edge */
AppHeader .header-spacer {
    width: 1fr;
}

/* Right: key hint */
AppHeader .header-key-hint {
    color: #56524C;
    width: auto;
}

/* Right: token count — rgba(245,240,232,0.50) ≈ #7C7872 */
AppHeader .header-tokens {
    color: #7C7872;
    width: auto;
}

/* Right: status dot */
AppHeader .header-status {
    color: #50fa7b;
    width: auto;
}

AppHeader .header-status.status-inactive {
    color: #56524C;
}

AppHeader .header-status.status-active {
    color: #50fa7b;
}

/* ── 2. CHAT BODY — READING COLUMN ─────────────────────────────────── */
ChatView {
    height: 1fr;
    min-height: 10;
    background: #0F0D0A;
    border: none !important;
    outline: none !important;
    padding: 1 1;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-size: 1 1;
    scrollbar-color: #28251F #0F0D0A;
}

ChatView.welcome-active {
    overflow-y: hidden;
    scrollbar-size: 0 0;
}

ScrollView {
    border: none !important;
    outline: none !important;
}

/* ── 3. MESSAGE VISUAL HIERARCHY ───────────────────────────────────── */

/* User messages: subtle tint + left border accent.
   No max-width — fills reading column width set by ChatView padding. */
UserBlock {
    height: auto;
    width: 1fr;
    background: #16140F;
    border-left: wide #28251F;
    padding: 0 3;
    margin: 0;
    margin-top: 2;
}

/* 4. LEFT-EDGE RHYTHM — AI messages get violet left rail */
AssistantBlock {
    height: auto;
    min-height: 1;
    width: 1fr;
    background: transparent;
    border-left: wide #7B6EAA;
    padding: 0 3 0 2;
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

/* System messages */
SystemLine {
    height: auto;
    min-height: 1;
    width: 100%;
    max-width: 112;
    background: transparent;
    border: none;
    color: #8C877E;
    text-style: italic;
    padding: 0 3;
    margin: 0;
    margin-top: 1;
}

/* Spinner */
LiveSpinner {
    height: 1;
    width: 100%;
    max-width: 112;
    background: transparent;
    border: none;
    margin: 0;
    margin-top: 1;
}

HorizontalRule {
    display: none;
}

/* ── BOTTOM BAR — docked bottom zone container ──────────────────────── */
#bottom-zone {
    height: auto;
    width: 100%;
    dock: bottom;
    background: transparent;
}

/* ── 6. BOTTOM INPUT ROW ──────────────────────────────────────────── */
InputRow {
    height: auto;
    min-height: 1;
    background: transparent;
    layout: vertical;
    padding: 0;
    margin: 0;
    border: none;
}

InputRow .input-top-rule {
    height: 1;
    width: 100%;
    color: #28251F;
    background: transparent;
    padding: 0;
    overflow: hidden hidden;
}

InputRow .input-bottom-rule {
    height: 1;
    width: 100%;
    color: #28251F;
    background: transparent;
    padding: 0;
    overflow: hidden hidden;
}

InputRow .input-line {
    height: 1;
    min-height: 1;
    layout: horizontal;
    background: transparent;
    padding: 0 3;
}

InputRow .prompt-char {
    width: 3;
    color: #7B6EAA;
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
    color: #F5F0E8;
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
    color: #56524C;
}

InputRow Horizontal {
    height: 1;
    min-height: 1;
    background: #0F0D0A;
    padding: 0 3;
}

/* ── Inline confirmation ─────────────────────────────────────────── */
InlineConfirmation {
    height: auto;
    width: 100%;
    max-width: 112;
    background: transparent;
    padding: 0 0 0 3;
    margin: 0;
}

InlineConfirmation .confirm-box {
    width: 72;
    max-width: 96%;
    height: auto;
    background: #1A1713;
    border-left: wide #C97C4A;
    border-top: none;
    border-right: none;
    border-bottom: none;
    padding: 0 1;
}

InlineConfirmation .confirm-title {
    height: 1;
    width: 100%;
    color: #8C877E;
    text-style: bold;
    padding: 0;
}

InlineConfirmation .confirm-command {
    height: 1;
    width: 100%;
    color: #F5F0E8;
    background: #0F0D0A;
    padding: 0 1;
    margin: 0;
}

InlineConfirmation .confirm-warning {
    height: auto;
    min-height: 1;
    width: 100%;
    background: transparent;
    color: #8C877E;
    padding: 0;
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
    background: #28251F;
    border: none;
    color: #8C877E;
}

InlineConfirmation .confirm-actions Button.selected {
    background: #C97C4A;
    color: #ffffff;
    text-style: bold;
}

InlineConfirmation .confirm-yes.selected {
    background: #8a4f3d;
}

InlineConfirmation .confirm-no.selected {
    background: #C97C4A;
}

InlineConfirmation.resolved .confirm-title {
    color: #56524C;
}

/* ── No API Keys onboarding ──────────────────────────────────────── */
NoAPIKeysOnboarding {
    height: auto;
    width: 100%;
    max-width: 84;
    background: transparent;
    padding: 0 0 0 2;
    margin: 2 0 0 0;
}

NoAPIKeysOnboarding .no-keys-box {
    width: 68;
    max-width: 100%;
    height: auto;
    background: #0F0D0A;
    border-left: solid #7B6EAA;
    padding: 0 0 0 2;
}

NoAPIKeysOnboarding .no-keys-title {
    height: 1;
    color: #F5F0E8;
    text-style: bold;
}

NoAPIKeysOnboarding .no-keys-copy {
    height: auto;
    min-height: 1;
    color: #8C877E;
    margin: 1 0 1 0;
}

NoAPIKeysOnboarding .no-keys-option {
    height: 1;
    width: 100%;
    color: #F5F0E8;
    background: transparent;
    margin: 0;
    padding: 0;
}

NoAPIKeysOnboarding .no-keys-option.selected {
    color: #F5F0E8;
    text-style: bold;
}

NoAPIKeysOnboarding .no-keys-shortcuts {
    height: 1;
    color: #56524C;
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

/* ── Footer row (below input row) ─────────────────────────────────────── */
#footer-row {
    height: 1;
    min-height: 1;
    width: 100%;
    background: #0F0D0A;
    padding: 0 2;
}

#model-bar {
    height: 1;
    min-height: 1;
    width: auto;
    max-width: 32;
    background: #0F0D0A;
    color: #A99DD1;
    padding: 0 1;
    margin: 0;
    border: none;
}

#model-bar:hover {
    background: #2A2558;
    color: #F5F0E8;
}

#footer-meta {
    height: 1;
    min-height: 1;
    width: 1fr;
    background: #0F0D0A;
    color: #56524C;
    padding: 0 1 0 2;
}

/* ── 7 & 8. Model selection modal ──────────────────────────────────── */
ModelSelectScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.60);
}

#model-panel {
    width: 60;
    height: auto;
    max-height: 34;
    background: #1A1713;
    border: solid #28251F;
}

#model-title-bar {
    height: auto;
    background: #1A1713;
    border-bottom: solid #28251F;
    padding: 0 2;
}

#model-title {
    height: 1;
    width: 100%;
    color: #F5F0E8;
    text-style: bold;
    padding: 0;
}

#model-search {
    height: 1;
    width: 100%;
    background: #0F0D0A;
    border: solid #28251F;
    color: #F5F0E8;
    padding: 0 2;
    margin: 1 1;
}

#model-search:focus {
    border: solid #7B6EAA;
}

#model-list {
    height: auto;
    max-height: 22;
    width: 100%;
    background: #1A1713;
    border: none;
    color: #F5F0E8;
    padding: 0;
    overflow-y: auto;
    scrollbar-size: 1 1;
    scrollbar-color: #28251F #1A1713;
}

/* CRITICAL FIX: selection highlight uses violet, NOT copper */
#model-list > .option-list--option {
    padding: 0 2;
    color: #F5F0E8;
}

#model-list > .option-list--option-highlighted {
    background: #2A2558;
    color: #F5F0E8;
    text-style: bold;
}

#model-list > .option-list--option-disabled {
    color: #56524C;
    text-style: bold;
    background: transparent;
    padding: 0 2;
}

#model-footer {
    height: 1;
    width: 100%;
    color: #56524C;
    background: #1A1713;
    border-top: solid #28251F;
    padding: 0;
}

/* ── Tool group selection modal ─────────────────────────────────────── */
ToolGroupSelectScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.60);
}

#tool-groups-panel {
    width: 78;
    height: auto;
    max-height: 18;
    background: #1A1713;
    border: solid #28251F;
}

#tool-groups-title-bar {
    height: auto;
    background: #1A1713;
    border-bottom: solid #28251F;
    padding: 0 2;
}

#tool-groups-title {
    height: 1;
    width: 100%;
    color: #F5F0E8;
    text-style: bold;
    padding: 0;
}

#tool-groups-list {
    height: auto;
    max-height: 8;
    width: 100%;
    background: #1A1713;
    border: none;
    color: #F5F0E8;
    padding: 0;
}

#tool-groups-list > .selection-list--option {
    padding: 0 2;
    color: #F5F0E8;
}

#tool-groups-list > .selection-list--option-highlighted {
    background: #2A2558;
    color: #F5F0E8;
}

#tool-groups-footer {
    height: 1;
    width: 100%;
    color: #56524C;
    background: #1A1713;
    border-top: solid #28251F;
    padding: 0;
}

/* ── 9. API Key list modal ───────────────────────────────────────────── */
APIKeyListScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.60);
}

#apikey-panel {
    width: 96;
    height: auto;
    max-height: 34;
    background: #1A1713;
    border: solid #28251F;
}

#apikey-title-bar {
    height: auto;
    background: #1A1713;
    border-bottom: solid #28251F;
    padding: 0 2;
}

#apikey-title {
    height: 1;
    width: 100%;
    color: #F5F0E8;
    text-style: bold;
    padding: 0;
}

#apikey-footer {
    height: 2;
    min-height: 2;
    width: 100%;
    background: #1A1713;
    border-top: solid #28251F;
    padding: 0;
}

#apikey-header-row {
    height: 1;
    width: 100%;
    background: #1A1713;
    padding: 0 2;
}

#apikey-list {
    height: auto;
    max-height: 18;
    width: 100%;
    background: #1A1713;
    border: none;
    color: #F5F0E8;
    padding: 0;
    overflow-y: auto;
    scrollbar-size: 1 1;
    scrollbar-color: #28251F #1A1713;
}

/* CRITICAL FIX: selection uses violet, NOT copper */
#apikey-list > .option-list--option {
    padding: 0 2;
    color: #F5F0E8;
}

#apikey-list > .option-list--option-highlighted {
    background: #2A2558;
    color: #F5F0E8;
}

#apikey-summary {
    height: auto;
    min-height: 1;
    width: 100%;
    background: #1A1713;
    padding: 0 2;
    color: #56524C;
}

/* ── 10. Add API Key modal ────────────────────────────────────────────── */
APIKeyAddScreen {
    align: center middle;
    background: rgba(0, 0, 0, 0.60);
}

#addkey-panel {
    width: 60;
    height: auto;
    max-height: 28;
    background: #1A1713;
    border: solid #28251F;
}

#addkey-title-bar {
    height: auto;
    background: #1A1713;
    border-bottom: solid #28251F;
    padding: 0 2;
}

#addkey-title {
    height: 1;
    width: 100%;
    color: #F5F0E8;
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
    color: #8C877E;
}

#addkey-form .field-hint {
    height: 1;
    margin: 0;
    padding: 0;
    color: #A99DD1;
    background: transparent;
}

#addkey-form Input {
    height: 1;
    width: 100%;
    background: #16140F;
    border: solid #28251F;
    color: #F5F0E8;
    padding: 0 1;
    margin: 0 0 0 0;
}

#addkey-form Input:focus {
    border: solid #7B6EAA;
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
    background: #C97C4A;
    color: #ffffff;
    text-style: bold;
    border: none;
}

#addkey-cancel {
    background: #28251F;
    color: #8C877E;
    border: none;
}

#addkey-footer {
    height: 1;
    width: 100%;
    color: #56524C;
    background: #1A1713;
    border-top: solid #28251F;
    padding: 0;
}

/* ── Welcome screen overlay ─────────────────────────────────────────── */
WelcomeScreen {
    layer: above;
    position: absolute;
    offset: 0 0;
    width: 100%;
    height: 100%;
    background: #0F0D0A;
    align: center middle;
    overflow: hidden hidden;
}

#welcome-content {
    width: 100%;
    height: 100%;
    color: #7B6EAA;
    text-style: bold;
    content-align: left top;
    overflow: hidden hidden;
}
/* ── Sudo password prompt ───────────────────────────────────────────── */
SudoPasswordPrompt {
    height: auto;
    width: 100%;
    max-width: 112;
    background: transparent;
    padding: 0 0 0 3;
    margin: 1 0;
}

SudoPasswordPrompt .sudo-prompt-box {
    width: 72;
    max-width: 96%;
    height: auto;
    background: #1A1713;
    border-left: wide #C97C4A;
    border-top: none;
    border-right: none;
    border-bottom: none;
    padding: 0 1;
}

SudoPasswordPrompt .sudo-prompt-title {
    height: 1;
    width: 100%;
    color: #C97C4A;
    text-style: bold;
    padding: 0;
}

SudoPasswordPrompt .sudo-prompt-hint {
    height: auto;
    min-height: 1;
    width: 100%;
    color: #8C877E;
    padding: 0;
}

SudoPasswordPrompt .sudo-prompt-input {
    height: 1;
    width: 100%;
    background: #0F0D0A;
    border: solid #28251F;
    color: #F5F0E8;
    padding: 0 1;
    margin: 1 0 0 0;
}

SudoPasswordPrompt .sudo-prompt-input:focus {
    border: solid #C97C4A;
}

SudoPasswordPrompt .sudo-prompt-keys {
    height: 1;
    width: 100%;
    color: #56524C;
    padding: 0;
    margin: 0;
}

SudoPasswordPrompt.resolved {
    display: none;
}
"""

DEFAULT_CSS = ASSISTANT_CSS
