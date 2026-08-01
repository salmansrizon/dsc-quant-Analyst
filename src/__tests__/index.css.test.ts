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

  // Spacing + radius scale (#87): structural, theme-independent tokens for a
  // dense financial UI. Named to avoid colliding with Tailwind v4's own
  // default `--radius-{xs,sm,md,lg,xl,2xl,3xl,4xl}` scale (already relied on
  // by rounded-sm/rounded-md elsewhere in the app) — a numbered radius scale
  // sidesteps that collision. Spacing uses tee-shirt names since Tailwind
  // ships no default named --spacing-* keys (only the bare multiplier used
  // by p-1/p-2/gap-1.../etc., which this does not touch). Safelisted via
  // @source inline so the utilities compile ahead of any consumer (#90/#97).
  const SPACING_RADIUS_UTILITIES = [
    ['p-xs', 'padding', '--spacing-xs'],
    ['p-sm', 'padding', '--spacing-sm'],
    ['p-md', 'padding', '--spacing-md'],
    ['p-lg', 'padding', '--spacing-lg'],
    ['p-xl', 'padding', '--spacing-xl'],
    ['gap-xs', 'gap', '--spacing-xs'],
    ['gap-sm', 'gap', '--spacing-sm'],
    ['gap-md', 'gap', '--spacing-md'],
    ['gap-lg', 'gap', '--spacing-lg'],
    ['gap-xl', 'gap', '--spacing-xl'],
    ['rounded-1', 'border-radius', '--radius-1'],
    ['rounded-2', 'border-radius', '--radius-2'],
    ['rounded-3', 'border-radius', '--radius-3'],
    ['rounded-4', 'border-radius', '--radius-4'],
    ['rounded-pill', 'border-radius', '--radius-pill'],
  ];

  it.each(SPACING_RADIUS_UTILITIES)(
    'compiles the scale utility .%s to %s: var(%s) via @theme + @source inline',
    async (className, property, themeVar) => {
      const output = await compile();
      expect(output).toMatch(
        new RegExp(`\\.${className}\\s*\\{[^}]*${property}:\\s*var\\(${themeVar}\\)`),
      );
    },
  );

  // Typography scale (#87): font-size/line-height tokens named by role
  // (micro/data/data-lg/heading) rather than by tee-shirt size, since
  // Tailwind's default --text-* namespace already reserves xs/sm/base/lg/
  // xl/2xl/3xl/4xl/5xl/6xl and text-xs/text-sm/text-lg/text-xl/text-2xl are
  // already relied on elsewhere in the app. --font-data is a tabular-figures
  // font stack for numeric/price data, additive alongside Tailwind's default
  // --font-sans/--font-serif/--font-mono. Safelisted via @source inline.
  const TYPE_UTILITIES = [
    ['text-micro', 'font-size', '--text-micro'],
    ['text-data', 'font-size', '--text-data'],
    ['text-data-lg', 'font-size', '--text-data-lg'],
    ['text-heading', 'font-size', '--text-heading'],
  ];

  it.each(TYPE_UTILITIES)(
    'compiles the scale utility .%s to %s: var(%s), with a matching line-height token',
    async (className, property, themeVar) => {
      const output = await compile();
      const rule = output.match(new RegExp(`\\.${className}\\s*\\{([^}]*)\\}`))?.[1];
      expect(rule).toBeDefined();
      expect(rule).toMatch(new RegExp(`${property}:\\s*var\\(${themeVar}\\)`));
      expect(rule).toMatch(new RegExp(`line-height:[^;]*var\\(${themeVar}--line-height\\)`));
    },
  );

  it('compiles .font-data to font-family: var(--font-data) via @theme + @source inline', async () => {
    const output = await compile();
    expect(output).toMatch(/\.font-data\s*\{[^}]*font-family:\s*var\(--font-data\)/);
  });

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

  // Motion tokens (#87): a short/base/slow duration scale and a small set of
  // easing curves for a dense financial UI, wired through @theme so they
  // compile as real theme variables, then consumed by hand-rolled
  // transition/micro-interaction utility classes (Tailwind v4 has no
  // named-key `--duration-*` utility generator, so these utilities are
  // hand-written rather than Tailwind-generated).
  const MOTION_UTILITIES = [
    ['transition-fast', '--duration-short', '--ease-standard'],
    ['transition-base', '--duration-base', '--ease-standard'],
    ['transition-slow', '--duration-slow', '--ease-standard'],
    ['value-flash', '--duration-short', '--ease-decisive'],
  ];

  it.each(MOTION_UTILITIES)(
    'compiles .%s using transition-duration: var(%s) and transition-timing-function: var(%s)',
    async (className, durationVar, easeVar) => {
      const output = await compile();
      const rule = output.match(new RegExp(`\\.${className}\\s*\\{([^}]*)\\}`))?.[1];
      expect(rule).toBeDefined();
      expect(rule).toMatch(new RegExp(`transition-duration:\\s*var\\(${durationVar}\\)`));
      expect(rule).toMatch(
        new RegExp(`transition-timing-function:\\s*var\\(${easeVar}\\)`),
      );
    },
  );

  it('keeps every motion utility governed by the single reduced-motion guard', async () => {
    const output = await compile();
    const reducedMotionBlock = output.match(
      /@media \(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*?)\n\}/,
    )?.[1];
    expect(reducedMotionBlock).toMatch(/\*,\s*\*::before,\s*\*::after/);

    for (const [className] of MOTION_UTILITIES) {
      const rule = output.match(new RegExp(`\\.${className}\\s*\\{([^}]*)\\}`))?.[1] ?? '';
      expect(rule).not.toMatch(/!important/);
      expect(rule).not.toMatch(/prefers-reduced-motion/);
    }
  });
});
