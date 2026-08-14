import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Bridge: some legacy tests were authored with `jest.fn()`. Map jest -> vi so
// they run under vitest without a rewrite. Prefer `vi` directly in new tests.
(globalThis as unknown as { jest: typeof vi }).jest = vi;

// jsdom doesn't implement ResizeObserver; Radix's Popper positioning (used by
// the #87 hover-popover primitive) reads it on mount.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

afterEach(() => {
  cleanup();
});
