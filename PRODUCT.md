# Product

## Register

product

## Users

A single expert **operator running their own self-hosted Capital trading engine**
(single login today, with `admin`/`user` roles). They know the domain cold —
markets, strategies, backtests, venues, AI decisioning — and use the app densely
and frequently. Design optimizes for one power user's daily monitoring and
intervention, not for onboarding newcomers or multi-tenant customers.

## Product Purpose

Capital is an algorithmic trading platform: it runs strategies across venues
(Binance spot/futures, Polymarket prediction markets), fetches and caches market
data, backtests strategies, and drives AI-assisted decisions (per-strategy AI
plus a multi-model "council"). The frontend is the operator's cockpit over that
engine.

The **primary day-to-day job is monitor-and-intervene**: see live positions,
P&L, strategy state and feed health at a glance, and step in fast (close a
position, confirm an AI signal in notify mode, flip a strategy's lifecycle) when
something needs a human. Deep work — backtesting, the Lab compare grid, research
reports, cost tracking, venue/AI configuration — is secondary but must stay
legible and trustworthy. Success = the operator trusts what the screen says and
can act on it without hunting.

## Brand Personality

**Precise · calm · trustworthy.** Voice is that of a Bloomberg-style terminal:
quiet, exact, unshowy. Restraint beats flash — the data is the hero and the UI
gets out of its way. It should feel like an instrument, not an app: something a
professional relies on with real capital at stake.

## Anti-references

Explicitly avoid all of these:

- **Gamified retail crypto** (Robinhood / Coinbase energy): confetti, gradient
  hero numbers, celebratory animations, streaks, dopamine UI. It trivializes
  real capital at risk.
- **Generic SaaS dashboard**: card-grid-everything, blue primary accent,
  hero-metric templates, uniformly rounded-friendly chrome. The AI-slop default.
- **Consumer fintech**: pastel, mascots, illustrations, playful onboarding
  wizards. Too soft for an expert tool.
- **Overloaded legacy terminal** (cluttered MT4 / ThinkorSwim): wall-of-widgets
  with no hierarchy or breathing room. Density is welcome; illegibility is not.

## Design Principles

1. **The data is the hero.** Chrome recedes; numbers, state, and charts lead.
   Restraint over decoration — if an element doesn't help the operator read or
   act, it doesn't ship.
2. **Legible at a glance, actionable in one step.** The critical state (P&L,
   positions, strategy health, feed staleness) must be readable instantly, and
   the matching intervention must never be more than a step away.
3. **Calm under real money.** No gamification, no dopamine tricks. The interface
   treats capital-at-risk with seriousness; it informs, it doesn't celebrate.
4. **Expert density without clutter.** Dense is correct for a power user, but
   hierarchy always survives the density. Information-rich ≠ noisy.
5. **Never signal by color alone.** Up/down, buy/sell, profit/loss carry a
   redundant cue (sign, arrow, shape, or position) so meaning survives
   colorblindness, grayscale, and a glance — color is reinforcement, not the
   only channel.

## Accessibility & Inclusion

Target **WCAG 2.1 AA**: ≥4.5:1 contrast for body text (≥3:1 for large), full
keyboard navigation with visible focus (the existing green `focus-ring`), and a
`prefers-reduced-motion` alternative for every animation (the pulse dots, caret
blink, and any reveal).

**Colorblind-safe is a hard requirement**, because the semantic system encodes
up/down and buy/sell/profit/loss with green (`#10b981`) and red (`#ef4444`)
only. Every such signal must pair the hue with a non-color cue (`+`/`−` sign,
▲/▼ arrow, or layout/position) so it reads correctly under red-green color
vision deficiency and in monochrome.
