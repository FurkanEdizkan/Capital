---
name: Capital
description: A dark, data-dense trading terminal for a solo operator — monochrome, precise, signal-only color.
colors:
  bg: "#08080a"
  surface: "#101012"
  card: "#141416"
  card-2: "#18181b"
  elev: "#1c1c20"
  border: "#232328"
  border-soft: "#1b1b1f"
  text: "#f4f4f5"
  text-2: "#a1a1aa"
  text-3: "#71717a"
  text-4: "#52525b"
  signal-green: "#10b981"
  signal-green-text: "#34d399"
  signal-red: "#ef4444"
  signal-red-text: "#f87171"
typography:
  title:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "10.5px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.02em"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "-0.01em"
    fontFeature: "tabular-nums"
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
components:
  button-default:
    backgroundColor: "{colors.card-2}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "32px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-2}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "32px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "32px"
  input:
    backgroundColor: "{colors.card-2}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "0 10px"
    height: "32px"
  badge-green:
    backgroundColor: "{colors.signal-green}"
    textColor: "{colors.signal-green-text}"
    rounded: "{rounded.xs}"
    padding: "2px 6px"
  badge-red:
    backgroundColor: "{colors.signal-red}"
    textColor: "{colors.signal-red-text}"
    rounded: "{rounded.xs}"
    padding: "2px 6px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "0"
---

# Design System: Capital

## 1. Overview

**Creative North Star: "The Trading Terminal"**

Capital is an instrument, not an app. It borrows the lineage of the professional
trading terminal — Bloomberg, a broker's blotter, an exchange's order book — where
the screen is a precision tool a professional relies on with real capital at
stake. The interface is near-black, monochrome, and dense; it recedes so that the
numbers, positions, and charts are the loudest thing on screen. Color is almost
absent by design: the only hues in the entire system are one green and one red,
and they mean exactly one thing — direction and outcome (up/buy/profit,
down/sell/loss). Everything else is a calibrated grayscale.

The personality is **precise, calm, and trustworthy**. It never celebrates, never
gamifies, never decorates. A profit is stated, not applauded. Density is welcome
because the user is a fluent expert, but hierarchy always survives the density —
information-rich is never the same as noisy. Motion is fast and functional
(120–140ms state transitions), never choreographed; the operator is in flow and
should never wait for the UI to finish animating.

This system explicitly rejects four things: **gamified retail crypto** (Robinhood/
Coinbase confetti, gradient hero numbers, dopamine UI), the **generic SaaS
dashboard** (card-grid-everything, blue primary, hero-metric templates), **consumer
fintech** softness (pastel, mascots, illustration, playful wizards), and the
**overloaded legacy terminal** (a cluttered wall of widgets with no hierarchy).
Dense but legible; quiet but exact.

**Key Characteristics:**
- Near-black tonal surfaces, monochrome grayscale ramp, flat by default.
- Signal-only color: one green, one red, meaning direction/outcome — nothing else.
- Inter for UI, JetBrains Mono with tabular figures for every number.
- Compact 13px base; small radii (4–8px); 1px borders instead of shadows.
- Fast, state-only motion; no page-load choreography.

## 2. Colors

A calibrated grayscale from near-black to near-white, punctuated by exactly two semantic hues.

### Primary
- **Signal Green** (`#10b981`, text-on-dark `#34d399`): the up/buy/profit signal. Used on P&L that is positive, buy-side badges, upward chart lines, live/healthy status dots, and the focus ring. Its scarcity is its power — it is a signal, not an accent.
- **Signal Red** (`#ef4444`, text-on-dark `#f87171`): the down/sell/loss signal. Used on negative P&L, sell-side badges, downward chart lines, and alert/stale status. The mirror of Signal Green and equally rationed.

### Neutral
- **Void** (`#08080a`): the base body background — the terminal's black.
- **Surface / Card / Card-2 / Elevated** (`#101012` → `#141416` → `#18181b` → `#1c1c20`): the tonal layering ramp. Each step up the ramp is one level of nesting or elevation. Panels, cards, controls, and popovers climb this ladder.
- **Border** (`#232328`) / **Border-soft** (`#1b1b1f`): 1px structural strokes. `border` separates surfaces; `border-soft` divides within a surface (section headers, table rows).
- **Ink ramp** (`#f4f4f5` → `#a1a1aa` → `#71717a` → `#52525b`): text from primary through secondary, tertiary, to quaternary. Primary ink for values, descending for labels and metadata. Never drop body text below `text-2` for readable content.

### Named Rules
**The Two-Signal Rule.** The only chromatic colors in the entire UI are Signal Green and Signal Red. Amber, blue, and violet were deliberately neutralized to grays and must stay that way. If a new element "needs a color," it doesn't — it needs a place on the grayscale ramp.

**The Signal-Not-Decoration Rule.** Green and red never appear for emphasis, branding, or flavor. They appear only where they carry directional/outcome meaning, and always alongside a non-color cue (see Do's and Don'ts).

## 3. Typography

**Body / UI Font:** Inter (with system-ui, -apple-system, Segoe UI fallback)
**Numeric / Mono Font:** JetBrains Mono (with ui-monospace, SFMono-Regular, Menlo fallback)

**Character:** One humanist sans carries every text role — heading, label, body — tuned tight and small for density. The only pairing is on a true contrast axis: a monospace with tabular figures for all numbers, so columns of prices, quantities, and P&L align to the pixel and never reflow as digits change. Base size is a deliberate 13px; this is a terminal, not a marketing page.

### Hierarchy
- **Title** (Inter 600, 13px, 1.45): section headers and panel titles. Sits on a `border-soft` divider.
- **Body** (Inter 400, 13px, 1.45): default UI text and prose. Cap prose at 65–75ch; tables may run denser.
- **Label** (Inter 600, 10.5–11.5px, +0.02em, UPPERCASE): badges and small status tags. The only place tracking and uppercase are used.
- **Mono** (JetBrains Mono 500, 13px, −0.01em, tabular-nums): every number that matters — prices, quantities, P&L, percentages, timestamps, IDs.

### Named Rules
**The Tabular Numbers Rule.** Every figure a user reads or compares is set in JetBrains Mono with `font-variant-numeric: tabular-nums`. Financial data in a proportional font is forbidden — misaligned digits are a legibility bug, not a style choice.

**The One-Family Rule.** Inter does headings, labels, and body. No display face, no second sans. Contrast comes from weight (400/500/600) and the mono axis, not from a new typeface.

## 4. Elevation

The system is **flat by default**. There is no decorative shadow. Depth is communicated entirely through the tonal surface ramp (`bg` → `surface` → `card` → `card-2` → `elev`) plus 1px borders: a nested or raised element is one step lighter than its parent and outlined with `border`. This keeps the terminal calm and matte — nothing floats without reason.

### Shadow Vocabulary
- **Terminal shadow** (`box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset, 0 1px 2px rgba(0,0,0,0.4)`): a near-invisible top inset highlight + a tight drop. Reserved for genuinely floating layers (modals, drawers, popovers) that must escape the tonal ramp — never on resting cards.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat and matte at rest. If you reach for a shadow to separate two resting elements, use a tonal step and a 1px border instead. Shadow appears only when a layer truly overlays the page (modal, drawer, popover).

## 5. Components

Component philosophy: **refined and restrained**. Controls are low-chrome and recede until needed; the 6px radius is the workhorse, borders do the structural work, and every state transition is a fast 120ms.

### Buttons
- **Shape:** gently rounded (6px, `rounded.sm`); 32px default height, 28px small.
- **Default:** filled with `card-2` (`#18181b`), `text` label, 1px `border`; hover lifts the fill to `#1f1f22`.
- **Ghost:** transparent with `text-2` label; hover fills `#1b1b1f` and brightens to `text`. For secondary/toolbar actions.
- **Outline:** transparent with 1px `border` and `text` label; hover fills `#1b1b1f`.
- **Hover / Focus:** background/border/color transition at 120ms ease; focus shows the green `focus-ring` (2px `signal-green`, 1px offset).

### Badges & Pills
- **Badge:** uppercase Label type (10.5–11.5px, 600, +0.02em), 4px radius, 2–3px×6–8px padding. Tones: `muted` (grayscale, the default), `green`, `red` — green/red tones use a tinted background (`green-bg`/`red-bg`) with a ~30%-opacity hued border and brightened text (`#34d399`/`#f87171`) for contrast on dark.
- **Pill:** 999px radius, `text-2` on `rgba(255,255,255,.03)` with a 1px `border`; for counts and passive tags.

### Inputs & Fields
- **Style:** `card-2` fill, 1px `border`, 6px radius, 32px default height; inner field is transparent, 13px, with `text-3` prefix/suffix affordances.
- **Toggle:** pill track, `#27272a` off / `signal-green` on, white knob, 140ms transition.
- **Focus:** green `focus-ring` (2px `signal-green`), consistent with buttons.

### Navigation & Selection
- **Tabs:** 12.5px/500 items, active gets `text` + `card-2` fill on a 6px radius; inactive is `text-3`.
- **SegmentedControl:** `card-2` track with 3px inset padding; the active segment lifts to `elev` (`#1c1c20`) on a 4px radius.

### Signature Components
- **DataTable:** the core surface — dense rows divided by `border-soft`, mono tabular columns for all figures. Density is the point.
- **Money / Pct:** render financial values in mono tabular-nums and apply Signal Green/Red by sign — always paired with the `+`/`−` sign so the value reads without color.
- **BuySellBadge / SideBadge:** buy = green tone, sell = red tone, with the word "BUY"/"SELL" carrying the meaning independent of hue.
- **EmptyState:** teaches the interface (what this panel is for, the action to take) rather than saying "nothing here."
- **Kbd:** monospace keycap for keyboard shortcuts — the operator is keyboard-driven.

## 6. Do's and Don'ts

### Do:
- **Do** keep color to the Two-Signal Rule: one green, one red, meaning direction/outcome only. Everything else lives on the grayscale ramp.
- **Do** pair every green/red signal with a non-color cue — a `+`/`−` sign, ▲/▼ arrow, "BUY"/"SELL" text, or position — so P&L and side read correctly under red-green color-vision deficiency and in grayscale. **This is a hard accessibility requirement, not a nicety.**
- **Do** set every number in JetBrains Mono with tabular figures so columns align.
- **Do** convey depth with the tonal ramp + 1px borders; reserve the terminal shadow for true overlays (modal/drawer/popover).
- **Do** keep motion fast (120–150ms) and tied to state; provide a `prefers-reduced-motion` alternative for the pulse dots and caret blink.
- **Do** hit WCAG AA contrast; keep readable body text at `text-2` or brighter, never `text-3`/`text-4`.

### Don't:
- **Don't** ship gamified retail-crypto patterns: no confetti, gradient hero numbers, celebratory animations, or dopamine streaks. Real capital is at risk.
- **Don't** fall into the generic SaaS dashboard: no card-grid-everything, no blue primary accent, no hero-metric template blocks.
- **Don't** drift toward consumer fintech softness: no pastels, mascots, illustrations, or playful onboarding wizards.
- **Don't** become the overloaded legacy terminal: density is welcome, but never at the cost of hierarchy and breathing room.
- **Don't** introduce a third hue, gradient text, or `background-clip: text`. If it "needs a color," it needs a grayscale value.
- **Don't** use a display font or a second typeface in UI, labels, or data — Inter + mono only, contrast via weight.
- **Don't** add decorative shadows or glassmorphism to resting surfaces.
