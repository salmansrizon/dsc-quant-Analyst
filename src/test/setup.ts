import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Bridge: some legacy tests were authored with `jest.fn()`. Map jest -> vi so
// they run under vitest without a rewrite. Prefer `vi` directly in new tests.
(globalThis as unknown as { jest: typeof vi }).jest = vi;

afterEach(() => {
  cleanup();
});
