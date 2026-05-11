## What's Working

The bones are solid. The layout hierarchy is clear, the tool trace line is a genuinely clever pattern, and the personality in the AI responses ("Don't tell me you were talking to someone else before me...") is a strong differentiator. The status bar at the bottom with model name is good information architecture.

---

## Structural Changes

**1. Top bar needs more intentionality.**
Right now it's just text scattered across a dark strip. It should be a proper chrome bar — `Assistant` title left-aligned as a true identity anchor, model + token count right-aligned as live metadata, with a subtle `0.5px` bottom border separating it from the chat body. Give it a slightly elevated background (`--ag-dark-surface` `#1A1713`) versus the chat background (`#0F0D0A`) so it reads as a distinct layer.

**2. The chat body lacks a reading column.**
Text runs edge-to-edge at full terminal width. This is the single biggest structural issue. Constrain the content to a max-width column (~900px, centered or left-biased), with generous horizontal padding. This is what separates "terminal app" from "premium terminal app." Wide lines are fatiguing; a reading column breathes.

**3. Message separation is too subtle.**
User messages and AI responses blur together. Right now user input sits on a slightly highlighted row, which is easy to miss. Strengthen the visual hierarchy: user messages get a muted `rgba(245,240,232,0.08)` left-border line (2px) + slight left-indent, AI responses get no border but a bit more vertical spacing above. This creates a clear call-and-response rhythm without adding color noise.

**4. Tool trace block needs enclosure.**
The `✓ shell_command docker info ▼` line floats inline. It should be a discrete indented block — a left-border in `#7B6EAA` (accent violet), `#1A1713` background, `8px` border-radius. Collapsed by default with an expand toggle. This makes tool use feel like a first-class design element, not a log line.

**5. The bottom input row needs weight.**
The `> _` prompt is very sparse. It deserves a full-width input row with a visible `0.5px` top border separating it from chat, consistent padding, and the cursor blinking in `#7B6EAA`. The status bar below (model name) should also have a cleaner separator.

**6. Modals need a backdrop blur.**
The API key manager and model picker currently sit on a hard dark background. Add `backdrop-filter: blur(4px)` + `rgba(0,0,0,0.6)` overlay. This adds depth and makes the modal feel like it's floating above the terminal rather than replacing it.

**7. Model picker needs grouped visual rhythm.**
The group headers (`— Gemini —`, `— Gemma —`) are barely legible. Make them proper eyebrow labels: `10px`, `letter-spacing: 0.1em`, `rgba(245,240,232,0.30)` — understated dividers between sections. The selected item highlight (`#C97C4A` warm copper) is a good instinct but conflicts with the design system's rule that warm = caution. Switch the selection highlight to `#7B6EAA` (accent violet) with `rgba(123,110,170,0.15)` background.

---

## Theme Corrections (against the Design System)

The current implementation diverges from the DESIGN_SYSTEM.MD in a few key ways:

| Issue | Current | Correct per DS |
|---|---|---|
| Selected row highlight | Warm copper `#C97C4A` | Accent violet `#7B6EAA` |
| API key hint color | Orange/copper | Should be `#A99DD1` (accent-mid) |
| Tool execution color | Orange copper | ✓ correct, `#C97C4A` is right here |
| Background | Looks close to pure black | Should be `#0F0D0A` (warm near-black) |
| Status active dot | Green — fine | Keep it |
| Input field background | Very dark, nearly invisible | `rgba(245,240,232,0.05)` with `0.5px` border |
| "Save" button | Warm copper fill | ✓ correct for a confirm action |
| Border thickness | Appears to be 1px | Must be `0.5px` throughout |

The biggest semantic violation is using warm copper for selection highlights (model picker, selected API key row). The design system is explicit: **warm = caution/destructive only**. Selection = agent action = violet.

---

## Layout Improvements

**Spacing system:** Introduce an 8px base grid strictly. Everything — padding, gap, margin — should be a multiple of 8. Right now spacing feels arbitrary.

**Vertical rhythm in chat:** Each exchange (user → AI) should have `32px` gap between it and the next exchange. Within an exchange, tool trace gets `8px` top margin. This creates breathing room without wasting screen space.

**Status bar:** Move from inline text to a proper two-zone bar — left zone for session info (model, key hint), right zone for token count. Monospaced font (`DM Mono`) for the numbers.

**Modal sizing:** The API key modal is well-sized. The model picker modal should be narrower (~480px max) with a fixed-height scrollable list area and a sticky search bar pinned at top.

**Typography pass:** Apply the DS type scale strictly — body at `14px/1.7`, captions at `12px`, labels at `10px` uppercase with `0.1em` tracking. The current implementation looks like it's using consistent `14px` for everything, which flattens the hierarchy.

---

## The One Thing That Would Transform It

**A visible left-edge rhythm.** Right now the layout is flat horizontal. If you add a persistent `2px` left rail — accent violet for AI turns, invisible for user turns — and indent all content from it, the whole TUI immediately reads as intentionally designed. It's the difference between a log file and an interface.

This single structural choice, combined with the reading column constraint, would make it feel like a premium tool that someone spent real time on.