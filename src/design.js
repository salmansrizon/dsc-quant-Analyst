// All values are CSS custom-property references resolved via [data-theme] on <html>.
// Swapping the attribute re-colors every inline style in the app instantly.
export const colors = {
  bg:                  'var(--color-bg)',
  surface:             'var(--color-surface)',
  surface2:            'var(--color-surface2)',
  border:              'var(--color-border)',
  accent:              'var(--color-accent)',
  accentHover:         'var(--color-accent-hover)',
  accentSubtle:        'var(--color-accent-subtle)',
  accentSubtleHover:   'var(--color-accent-subtle-hover)',
  textPrimary:         'var(--color-text-primary)',
  textSecondary:       'var(--color-text-secondary)',
  green:               'var(--color-green)',
  red:                 'var(--color-red)',
  yellow:              'var(--color-yellow)',
  gradientBrand:       'var(--gradient-brand)',
};

export const card = {
  background:   'var(--color-surface)',
  border:       '1px solid var(--color-border)',
  borderRadius: 10,
  padding:      '16px 18px',
  boxShadow:    'var(--shadow-sm)',
};
