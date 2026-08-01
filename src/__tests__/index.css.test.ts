import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import postcss from 'postcss';
import postcssrc from 'postcss-load-config';

// Login.tsx:69 uses `bg-indigo-600` — a Tailwind-only utility with no
// hand-rolled equivalent in index.css. Its presence in the compiled output
// proves Tailwind is installed, wired into the real PostCSS config, and
// scanning src/** for class usage.
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const CSS_PATH = path.join(REPO_ROOT, 'src/index.css');

async function compile() {
  const css = fs.readFileSync(CSS_PATH, 'utf8');
  const { plugins, options } = await postcssrc({}, REPO_ROOT);
  const result = await postcss(plugins).process(css, { ...options, from: CSS_PATH });
  return result.css;
}

describe('src/index.css PostCSS pipeline', () => {
  it('compiles the Tailwind-only utility bg-indigo-600 used in Login.tsx', async () => {
    const output = await compile();
    expect(output).toMatch(/\.bg-indigo-600\s*\{[^}]*background-color:/);
  });

  it('preserves the hand-rolled .flex utility with its original declaration', async () => {
    const output = await compile();
    expect(output).toMatch(/\.flex\s*\{\s*display:\s*flex;?\s*\}/);
  });
});
