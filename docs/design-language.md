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

3. **Structural tokens** (#87) — spacing, radius, motion (duration/easing),
   and typography. Unlike the base and semantic layers, these don't vary by
   theme, so each is declared once in the `@theme` block itself rather than
   split across `:root` / `[data-theme='dark']`.

   - **Spacing** — `--spacing-xs` … `--spacing-xl`, a tighter tee-shirt
     scale (4px–24px) than a general-purpose app, for dense tables and
     grids. Exposed as `p-xs`…`p-xl` and `gap-xs`…`gap-xl`. Additive: it
     doesn't touch Tailwind's own bare `--spacing` multiplier, which the
     existing numeric utilities (`p-1`, `gap-4`, …) already read from.
   - **Radius** — `--radius-1` … `--radius-4` (2px–12px) plus
     `--radius-pill` (999px), exposed as `rounded-1`…`rounded-4` and
     `rounded-pill`. Numbered rather than xs/sm/md/lg/xl on purpose:
     Tailwind v4 ships a default `--radius-*` scale under those exact
     names, and `rounded-sm`/`rounded-md` are already relied on elsewhere
     in the app — reusing those names would have silently redefined them
     app-wide.
   - **Typography** — `--text-micro`, `--text-data`, `--text-data-lg`,
     `--text-heading` (each with a matching `--text-*--line-height`), plus
     the `--font-data` tabular-figures font stack for numeric/price
     values. Exposed as `text-micro`/`text-data`/`text-data-lg`/
     `text-heading` and `font-data`. Named by role rather than tee-shirt
     size for the same reason as radius: Tailwind's default `--text-*`
     scale (`xs`, `sm`, `base`, `lg`, `xl`, `2xl`, `3xl`, …) is already in
     use (`text-xs`, `text-lg`, `text-2xl`, …).
   - See **Motion** below for `--duration-*` / `--ease-*`.

   Spacing, radius, and typography each generate real Tailwind utilities
   from their `@theme` keys, so — like the semantic color tokens — they're
   safelisted via the same `@source inline(...)`, for the same reason:
   Tailwind v4 tree-shakes any utility not referenced in scanned source, and
   this token surface is meant to exist ahead of its first consumer (#90,
   #97). Motion tokens are the exception; see **Motion** below for why.

## Motion

`prefers-reduced-motion: reduce` neutralizes every animation and transition
duration app-wide (`index.css`, near the responsive rules), including the
existing `.transition-all` / `.hover-lift` / keyframe animations and any
transition utility added on top of the semantic tokens above. New motion
should ride on `transition`/`animation` properties rather than JS-driven
timers, so it stays covered by this single rule instead of needing its own
reduced-motion opt-out.

### Motion tokens (#87)

A short/base/slow duration scale and a small set of easing curves, tuned for
a dense financial UI (quick, low-travel feedback rather than showy motion):

- `--duration-short` (100ms) — hover/focus feedback, `.value-flash`.
- `--duration-base` (180ms) — the default for most transitions.
- `--duration-slow` (320ms) — larger layout shifts (panel expand/collapse).
- `--ease-standard` — general-purpose deceleration curve.
- `--ease-decisive` — snappier curve for emphasis (price-tick flashes).
- `--ease-linear` — continuous/ticking motion.

These are declared directly in the `@theme` block (see **Token layers** #3
above) rather than in `:root`/`[data-theme='dark']`, since they don't vary
by theme. Tailwind v4 has no named-key `--duration-*` utility generator (only
numeric `duration-150`-style values), so instead of relying on Tailwind to
emit utilities from these tokens, `index.css` hand-rolls a small set of
transition utilities on top of them: `.transition-fast`, `.transition-base`,
`.transition-slow`, and `.value-flash` (a micro-interaction for a data value
that just updated). Because these are plain CSS classes rather than
Tailwind-generated ones, they aren't subject to `@source inline(...)`
safelisting — they're never tree-shaken, the same as `.card`/`.btn-primary`.
Being plain `transition-duration`/`transition-timing-function` declarations
with no `!important` or `prefers-reduced-motion` logic of their own, they're
neutralized by the single reduced-motion guard exactly like every other
transition in the file.
