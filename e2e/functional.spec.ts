import { test, expect } from '@playwright/test';

/**
 * Authenticated feature walk (#114) against real BigQuery.
 *
 * Signup appends a real row to the append-only `users` table, so this is
 * gated behind E2E_WRITE=1 to keep the default suite read-only. Run with:
 *   E2E_WRITE=1 npx playwright test functional
 */
const WRITE = process.env.E2E_WRITE === '1';

test.describe('authenticated feature walk', () => {
  test.skip(!WRITE, 'set E2E_WRITE=1 to run (signup writes a real BigQuery row)');

  const email = `e2e+${Date.now()}@example.com`;
  const password = 'Test-Passw0rd!';

  // Signup + login each drive a BigQuery load/read job (~7s signup observed),
  // so this flow needs a generous budget.
  test.setTimeout(90_000);

  test('signup -> dashboard -> screener -> stock detail render real data', async ({ page }) => {
    await page.goto('/signup');
    await page.locator('#full_name').fill('E2E Bot');
    await page.locator('#email').fill(email);
    await page.locator('#phone').fill('01700000000');
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: 'Sign up' }).click();

    // Auto-logged in -> lands on the dashboard (allow for the slow BQ writes).
    await page.waitForURL((u) => u.pathname === '/', { timeout: 45_000 });
    await expect(page.getByText(/stocks|market|feed/i).first()).toBeVisible();

    // Screener returns real rows after running filters.
    await page.goto('/screener');
    await page.getByRole('button', { name: /run filters/i }).click();
    await expect(page.getByText(/Symbol/i).first()).toBeVisible();

    // Stock detail for a known DSE symbol renders + shows the ticker.
    await page.goto('/stock/ABBANK');
    await expect(page.getByText(/ABBANK/i).first()).toBeVisible();
  });
});
