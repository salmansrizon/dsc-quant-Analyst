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

  it('preserves the hand-rolled .card utility with its original declaration', async () => {
    const output = await compile();
    expect(output).toMatch(/\.card\s*\{\s*background:\s*var\(--bg-secondary\);/);
  });

  // Semantic design tokens (#87): named by meaning (gain/loss/neutral,
  // elevation, border tone) rather than by hue, so components read
  // `text-gain` instead of `text-accent-green`. Safelisted via
  // `@source inline(...)` in index.css so the utilities compile ahead of
  // any consumer (#97/#98) — Tailwind v4 otherwise tree-shakes utilities
  // that aren't referenced yet in scanned source.
  const SEMANTIC_UTILITIES = [
    ['text-gain', 'color', '--color-gain'],
    ['text-loss', 'color', '--color-loss'],
    ['text-neutral', 'color', '--color-neutral'],
    ['bg-gain', 'background-color', '--color-gain'],
    ['bg-loss', 'background-color', '--color-loss'],
    ['bg-elevated-1', 'background-color', '--color-elevated-1'],
    ['bg-elevated-2', 'background-color', '--color-elevated-2'],
    ['border-border-subtle', 'border-color', '--color-border-subtle'],
    ['border-border-strong', 'border-color', '--color-border-strong'],
  ];

  it.each(SEMANTIC_UTILITIES)(
    'compiles the semantic utility .%s to %s: var(%s) via @theme + @source inline',
    async (className, property, themeVar) => {
      const output = await compile();
      const escapedClass = className.replace(/\./g, '\\.');
      expect(output).toMatch(
        new RegExp(`\\.${escapedClass}\\s*\\{[^}]*${property}:\\s*var\\(${themeVar}\\)`),
      );
    },
  );

  const PRE_EXISTING_VARS = [
    '--bg-primary',
    '--bg-secondary',
    '--text-primary',
    '--text-secondary',
    '--accent-blue',
    '--accent-green',
    '--accent-red',
    '--border-color',
    '--body-gradient',
  ];

  const NEW_SEMANTIC_VARS = [
    '--gain',
    '--loss',
    '--neutral',
    '--elevated-1',
    '--elevated-2',
    '--border-subtle',
    '--border-strong',
  ];

  it.each([...PRE_EXISTING_VARS, ...NEW_SEMANTIC_VARS])(
    'defines %s in both :root and [data-theme="dark"]',
    async (name) => {
      const output = await compile();
      const rootBlock = output.match(/:root\s*\{([^}]*)\}/)?.[1] ?? '';
      const darkBlock = output.match(/\[data-theme=[`'"]dark[`'"]\]\s*\{([^}]*)\}/)?.[1] ?? '';
      expect(rootBlock).toMatch(new RegExp(`${name}:`));
      expect(darkBlock).toMatch(new RegExp(`${name}:`));
    },
  );

  it('neutralizes transitions and animations under prefers-reduced-motion: reduce', async () => {
    const output = await compile();
    const reducedMotionBlock = output.match(
      /@media \(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?)\n\}/,
    )?.[1];
    expect(reducedMotionBlock).toBeDefined();
    expect(reducedMotionBlock).toMatch(/transition-duration:\s*0\.01ms\s*!important/);
    expect(reducedMotionBlock).toMatch(/animation-duration:\s*0\.01ms\s*!important/);
  });
});
