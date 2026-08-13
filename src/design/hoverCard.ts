// Shared Radix HoverCard shell (#87's hover-popover primitive, reused by #89's
// FitScorecard) — one source of truth for the timing and the content/arrow
// styling so a palette or spacing change doesn't have to be repeated per caller.
export const HOVER_CARD_OPEN_DELAY = 150;
export const HOVER_CARD_CLOSE_DELAY = 100;

export const HOVER_CARD_CONTENT_CLASS =
  'max-w-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--text-primary)] shadow-[var(--shadow-elevated)]';

export const HOVER_CARD_ARROW_CLASS = 'fill-[var(--bg-elevated)]';
