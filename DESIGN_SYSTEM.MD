# Agens Design System

## Philosophy
Warm parchment meets infrastructure precision. The aesthetic is aged paper and quiet confidence — not the cool grays of typical dev tools, not stark white SaaS. Every surface carries a slight warmth. Dark mode mirrors this with near-black warm tones, never pure black.

Two signal colors do all the work. Everything else is neutral.

---

## Color Palette

### Light Mode (Web)

| Token | Hex | Usage |
|---|---|---|
| `--ag-warm-white` | `#FAF8F4` | Input backgrounds, elevated surfaces |
| `--ag-cream` | `#F5F0E8` | Page background |
| `--ag-surface` | `#EEEAE1` | Cards, sidebar, secondary surfaces |
| `--ag-border` | `#D4CEBC` | All borders (0.5px) |
| `--ag-ink` | `#1C1814` | Primary text, primary buttons |
| `--ag-ink-2` | `#4A4237` | Secondary text, labels |
| `--ag-ink-3` | `#8C8070` | Muted text, placeholders, captions |
| `--ag-accent` | `#7B6EAA` | Primary accent — links, focus rings, AI avatar, active states |
| `--ag-accent-mid` | `#A99DD1` | Accent hover states, subtle highlights |
| `--ag-accent-light` | `#EAE6F5` | Accent backgrounds — tool blocks, badges, soft highlights |
| `--ag-accent-deep` | `#5A4F8A` | Accent pressed/active |
| `--ag-accent-glow` | `rgba(123,110,170,0.15)` | Focus ring shadow only |
| `--ag-warm` | `#C97C4A` | Sudo confirm, destructive warnings, alerts — use sparingly |
| `--ag-warm-light` | `#F5EAE0` | Warm action button backgrounds |

### Dark Mode (TUI + Web dark)

| Token | Hex | Usage |
|---|---|---|
| `--ag-dark-bg` | `#0F0D0A` | Terminal / page background |
| `--ag-dark-surface` | `#1A1713` | Card / panel surfaces |
| `--ag-dark-border` | `rgba(255,255,255,0.07)` | Borders |
| `--ag-dark-text` | `rgba(245,240,232,0.85)` | Primary text |
| `--ag-dark-text-2` | `rgba(245,240,232,0.50)` | Secondary text, user messages |
| `--ag-dark-text-3` | `rgba(245,240,232,0.30)` | Muted, timestamps, captions |
| `--ag-accent` | `#7B6EAA` | Same accent — carries over unchanged |
| `--ag-accent-mid` | `#A99DD1` | Role labels, tool names in TUI |
| `--ag-warm` | `#C97C4A` | Sudo / warning — same warm copper |

---

## Typography

**Font:** DM Sans (primary). Fallback: `system-ui, -apple-system, sans-serif`.
**Mono font (TUI):** DM Mono or Fira Code.

| Role | Size | Weight | Notes |
|---|---|---|---|
| Display | 28px | 300 | Letter-spacing: -0.03em |
| Heading | 20px | 400 | Letter-spacing: -0.02em |
| Body | 14px | 400 | Line-height: 1.7 |
| Caption | 12px | 400 | Letter-spacing: 0.01em |
| Label / eyebrow | 10px | 500 | Uppercase, letter-spacing: 0.1em |

Never use font-weight 600 or 700. The system uses 300, 400, and 500 only. Sentence case always — no ALL CAPS in UI, no Title Case in labels.

---

## Border Radius

| Token | Value | Usage |
|---|---|---|
| `--r-sm` | `8px` | Badges, chips, small inputs |
| `--r-md` | `12px` | Buttons, input fields, tool blocks |
| `--r-lg` | `18px` | Cards, panels, chat bubbles |
| `--r-xl` | `24px` | Chat container, modal |

---

## Borders

All borders are `0.5px solid` — never 1px. Thin strokes read as precise and refined.

- Default: `0.5px solid #D4CEBC`
- Hover/emphasis: `0.5px solid rgba(60,50,30,0.22)`
- Accent: `0.5px solid rgba(123,110,170,0.25)`
- Warm/warning: `0.5px solid rgba(201,124,74,0.25)`
- Dark mode: `0.5px solid rgba(255,255,255,0.07)`

---

## Components

### Buttons

**Primary** — dark ink background, cream text. Hover darkens slightly.
```
background: #1C1814 | color: #F5F0E8 | border-radius: 12px | padding: 8px 18px
```

**Ghost** — transparent with border. Hover fills surface.
```
background: transparent | border: 0.5px solid #D4CEBC | color: #1C1814
Hover: background: #EEEAE1
```

**Accent** — for positive/constructive actions.
```
background: #EAE6F5 | color: #7B6EAA | border: 0.5px solid rgba(123,110,170,0.25)
```

**Warm/Sudo** — reserved exclusively for destructive or confirmation actions.
```
background: #F5EAE0 | color: #C97C4A | border: 0.5px solid rgba(201,124,74,0.25)
```

### Input Fields
```
background: #FAF8F4
border: 0.5px solid #D4CEBC
border-radius: 12px
padding: 10px 14px
font-size: 14px
color: #1C1814

Focus:
border-color: #7B6EAA
box-shadow: 0 0 0 3px rgba(123,110,170,0.15)
```

### Chat Bubbles (Web)

**AI bubble:**
```
background: #EEEAE1 | color: #1C1814
border-radius: 18px, with bottom-left: 4px
```

**User bubble:**
```
background: #1C1814 | color: #F5F0E8
border-radius: 18px, with bottom-right: 4px
```

**Avatars:**
- AI: `background: #EAE6F5 | color: #7B6EAA` — letter "A"
- User: `background: #EEEAE1 | color: #4A4237`

### Tool Execution Block (Web)
```
background: #EAE6F5
border: 0.5px solid rgba(123,110,170,0.20)
border-radius: 8px
padding: 7px 12px
font-size: 12px
color: #7B6EAA
```
Contains a small `6px` filled circle in `#A99DD1` followed by tool name and execution time.

---

## TUI (Terminal UI) Specifics

Background: `#0F0D0A` — warm near-black, not pure black.

**Role prefixes:**
- AI role label: `#A99DD1` (accent mid)
- User role label: `rgba(245,240,232,0.35)` (very muted)

**Text:**
- AI response text: `rgba(245,240,232,0.85)`
- User message text: `rgba(245,240,232,0.50)`

**Tool execution line:**
```
color: #C97C4A (warm copper)
prefix: ⚙ symbol
format: "⚙ tool_name · args · Xs"
```

**Input row:**
- Prompt symbol `›` in `#7B6EAA`
- Cursor: `7px × 13px` block, `background: #7B6EAA`, blink animation

**Section divider:** `0.5px solid rgba(255,255,255,0.07)`

**Window chrome dots (top bar):**
- Warm copper `#C97C4A`
- Accent mid `#A99DD1`
- Accent `#7B6EAA`

---

## Color Semantics (strict)

| Meaning | Color | Hex |
|---|---|---|
| AI / agent identity | Dusty violet | `#7B6EAA` |
| Destructive / sudo / warning | Warm copper | `#C97C4A` |
| Neutral structure | Ink scale | `#1C1814` → `#8C8070` |
| Surfaces / backgrounds | Cream scale | `#FAF8F4` → `#EEEAE1` |

Never use the accent or warm colors decoratively. Accent means "agent or action." Warm means "caution or confirmation required."

---

## What This Should Feel Like

Stripe-grade precision on warm parchment. The app should feel like a premium terminal tool that someone designed with intention — not assembled from a component library. Surfaces breathe. Text is never harsh. The two signal colors earn every pixel they occupy.