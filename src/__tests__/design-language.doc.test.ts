import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Lightweight regression guard, not a red/green TDD cycle — docs aren't
// "behavior". This just stops docs/design-language.md from silently rotting
// (e.g. losing the data-theme explanation) before #97/#98 rely on it.
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const DOC_PATH = path.join(REPO_ROOT, 'docs/design-language.md');

describe('docs/design-language.md', () => {
  it('exists and documents the data-theme mechanism', () => {
    const doc = fs.readFileSync(DOC_PATH, 'utf8');
    expect(doc).toMatch(/data-theme/);
    expect(doc).toMatch(/ThemeContext/);
  });

  it('documents every semantic token defined in index.css', () => {
    const doc = fs.readFileSync(DOC_PATH, 'utf8');
    const semanticTokens = [
      '--gain',
      '--loss',
      '--neutral',
      '--elevated-1',
      '--elevated-2',
      '--border-subtle',
      '--border-strong',
    ];
    for (const token of semanticTokens) {
      expect(doc).toContain(token);
    }
  });
});
