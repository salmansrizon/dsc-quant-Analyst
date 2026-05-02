---
name: design-system-tradingview-track-all-markets
description: Creates implementation-ready design-system guidance with tokens, component behavior, and accessibility standards. Use when creating or updating UI rules, component specifications, or design-system documentation.
---

<!-- TYPEUI_SH_MANAGED_START -->

# TradingView — Track All Markets

## Mission
Deliver implementation-ready design-system guidance for TradingView — Track All Markets that can be applied consistently across content site interfaces.

## Brand
- Product/brand: TradingView — Track All Markets
- URL: https://www.tradingview.com/
- Audience: readers and knowledge seekers
- Product surface: content site

## Style Foundations
- Visual style: structured, accessible, implementation-first
- Main font style: `font.family.primary=-apple-system`, `font.family.stack=-apple-system, system-ui, Trebuchet MS, Roboto, Ubuntu, sans-serif`, `font.size.base=14px`, `font.weight.base=400`, `font.lineHeight.base=normal`
- Typography scale: `font.size.xs=0px`, `font.size.sm=12px`, `font.size.md=14px`, `font.size.lg=16px`, `font.size.xl=18px`, `font.size.2xl=20px`, `font.size.3xl=28px`, `font.size.4xl=36px`
- Color palette: `color.text.primary=#0f0f0f`, `color.text.secondary=#0000ee`, `color.text.tertiary=#ffffff`, `color.text.inverse=#2962ff`, `color.surface.base=#000000`, `color.surface.muted=#f9f9f9`, `color.surface.strong=#2e2e2e`
- Spacing scale: `space.1=4px`, `space.2=8px`, `space.3=10px`, `space.4=11px`, `space.5=12px`, `space.6=14px`, `space.7=15px`, `space.8=16px`
- Radius/shadow/motion tokens: `radius.xs=4px`, `radius.sm=8px`, `radius.md=12px`, `radius.lg=14px`, `radius.xl=16px`, `radius.2xl=20px`, `radius.step7=36px`, `radius.step8=40px`

## Accessibility
- Target: WCAG 2.2 AA
- Keyboard-first interactions required.
- Focus-visible rules required.
- Contrast constraints required.

## Writing Tone
concise, confident, implementation-focused

## Rules: Do
- Use semantic tokens, not raw hex values in component guidance.
- Every component must define required states: default, hover, focus-visible, active, disabled, loading, error.
- Responsive behavior and edge-case handling should be specified for every component family.
- Accessibility acceptance criteria must be testable in implementation.

## Rules: Don't
- Do not allow low-contrast text or hidden focus indicators.
- Do not introduce one-off spacing or typography exceptions.
- Do not use ambiguous labels or non-descriptive actions.

## Guideline Authoring Workflow
1. Restate design intent in one sentence.
2. Define foundations and tokens.
3. Define component anatomy, variants, and interactions.
4. Add accessibility acceptance criteria.
5. Add anti-patterns and migration notes.
6. End with QA checklist.

## Required Output Structure
- Context and goals
- Design tokens and foundations
- Component-level rules (anatomy, variants, states, responsive behavior)
- Accessibility requirements and testable acceptance criteria
- Content and tone standards with examples
- Anti-patterns and prohibited implementations
- QA checklist

## Component Rule Expectations
- Include keyboard, pointer, and touch behavior.
- Include spacing and typography token requirements.
- Include long-content, overflow, and empty-state handling.

## Quality Gates
- Every non-negotiable rule must use "must".
- Every recommendation should use "should".
- Every accessibility rule must be testable in implementation.
- Prefer system consistency over local visual exceptions.

<!-- TYPEUI_SH_MANAGED_END -->
