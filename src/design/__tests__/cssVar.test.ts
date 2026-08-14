import { describe, expect, it } from 'vitest';
import { cssVar } from '../cssVar';

describe('cssVar', () => {
  it('resolves a custom property set on the document root', () => {
    document.documentElement.style.setProperty('--test-color', '#123456');
    expect(cssVar('--test-color', '#000000')).toBe('#123456');
    document.documentElement.style.removeProperty('--test-color');
  });

  it('falls back when the property is unset', () => {
    expect(cssVar('--totally-unset-var', '#abcdef')).toBe('#abcdef');
  });
});
