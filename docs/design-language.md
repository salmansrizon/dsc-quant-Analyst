# Design language

Source of truth: `src/index.css`. This doc explains the mechanism and the
token vocabulary; it doesn't restate values that can drift — read the CSS
for exact hex values.

## Theme switching (`data-theme`)

`ThemeContext` (#82) toggles a `data-theme="dark"` attribute on `<html>`.
`src/index.css` defines every themable value as a CSS custom property twice:
once in `:root` (light, the default) and once in `[data-theme='dark']`. No
component ever hardcodes a color — it reads `var(--token-name)`, either
directly or through a Tailwind utility generated from an `@theme` alias — so
flipping the attribute repaints the whole app with no re-render and no
per-component theme logic.

Adding a new themable value means adding it to **both** blocks. A value
present in only one block silently falls back to `initial`/inherited in the
other theme, which is why `src/__tests__/index.css.test.ts` asserts every
token is defined in both.

## Token layers

1. **Base tokens** (`--bg-primary`, `--bg-secondary`, `--text-primary`,
   `--text-secondary`, `--accent-blue`, `--accent-green`, `--accent-red`,
   `--border-color`, `--body-gradient`) — the original palette. Hand-rolled
   utility classes (`.card`, `.btn-primary`, `.text-accent-green`, …) consume
   these directly via `var()`.

2. **Semantic tokens** (#87) — named by *meaning*, not hue, so a component
   asks for what it means ("this number is a gain") rather than which color
   that happens to be today:
   - `--gain` / `--loss` / `--neutral` — aliases of `--accent-green` /
     `--accent-red` / `--text-secondary`. Use these (via `.text-gain`,
     `.text-loss`, `.bg-gain`, `.bg-loss`) for price-direction and
     status coloring instead of reaching for `--accent-*` by hue, so the
     accent palette can change without every gain/loss call site changing
     with it.
   - `--elevated-1` / `--elevated-2` — a two-step elevation scale.
     `--elevated-1` is the base raised surface (aliases `--bg-secondary`,
     i.e. the existing card surface); `--elevated-2` is one step further off
     the page, for content stacked above a card (popovers, dropdowns,
     modals).
   - `--border-subtle` / `--border-strong` — two border tones.
     `--border-subtle` aliases `--border-color` (the existing default);
     `--border-strong` is a higher-contrast tone for emphasis (active/focus
     containers, dividers that need to read clearly).

   These are exposed as Tailwind utilities (`text-gain`, `bg-elevated-2`,
   `border-border-subtle`, etc.) through an `@theme` block in `index.css`
   that points `--color-*` theme keys at the runtime custom properties above.
   Tailwind v4 only compiles a utility that's referenced in scanned source,
   so `index.css` pre-declares the intended set via `@source inline(...)` —
   this lets the token surface exist ahead of its first consumer (#97, #98)
   instead of being invented ad hoc per component.

## Motion

`prefers-reduced-motion: reduce` neutralizes every animation and transition
duration app-wide (`index.css`, near the responsive rules), including the
existing `.transition-all` / `.hover-lift` / keyframe animations and any
transition utility added on top of the semantic tokens above. New motion
should ride on `transition`/`animation` properties rather than JS-driven
timers, so it stays covered by this single rule instead of needing its own
reduced-motion opt-out.
