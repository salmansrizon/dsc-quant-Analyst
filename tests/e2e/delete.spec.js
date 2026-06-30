import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

// The watchlist/portfolio mutations persist via BigQuery load jobs, which take
// several seconds. These tests wait for the app's own post-action refresh (or
// the modal to close) before reloading, so an in-flight request is never
// aborted by navigation.
test.describe('Deletion persists', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
  });

  test('removing a watchlist symbol persists across reload', async ({ page }) => {
    test.setTimeout(120000);
    await page.goto('http://localhost:5173/watchlist');
    // Unique symbol per run → no accumulation, and waiting for count==1 below
    // guarantees the (slow) add committed before we delete, avoiding a race.
    const sym = `WL${Date.now() % 100000}`;
    const rows = () => page.getByRole('main').getByRole('button', { name: sym, exact: true });

    const input = page.locator('input[placeholder*="Symbol"]');
    await expect(input).toBeVisible({ timeout: 10000 });
    await input.fill(sym);
    // Wait for the POST to actually commit server-side (the UI shows the row
    // optimistically before this resolves).
    const addResp = page.waitForResponse(r => r.url().includes('/api/watchlist') && r.request().method() === 'POST', { timeout: 25000 });
    await page.getByRole('button', { name: /^Add/ }).click();
    await addResp;
    await expect.poll(() => rows().count(), { timeout: 20000 }).toBe(1);

    // Delete via the row's trash button; wait for the DELETE to commit
    const delResp = page.waitForResponse(r => r.url().includes('/api/watchlist/') && r.request().method() === 'DELETE', { timeout: 25000 });
    await page.getByRole('button', { name: `Remove ${sym} from watchlist` }).first().click();
    await delResp;
    await expect.poll(() => rows().count(), { timeout: 25000 }).toBe(0);

    // Reload — the deletion must have persisted
    await page.reload();
    await expect.poll(() => rows().count(), { timeout: 15000 }).toBe(0);
  });

  test('removing a portfolio position persists across reload', async ({ page }) => {
    test.setTimeout(120000);
    await page.goto('http://localhost:5173/portfolio');
    await page.waitForTimeout(1000);
    // Unique symbol per run → baseline is deterministically 0 even if the slow
    // GET /portfolio hasn't rendered yet, and add/delete deltas are exact.
    const sym = `DEL${Date.now() % 100000}`;
    const rows = () => page.getByRole('main').getByText(sym, { exact: true });

    // Add the position; wait for the modal to close (POST resolved)
    await page.getByRole('button', { name: /Add Position/ }).click();
    const inputs = page.locator('div[role="dialog"] input');
    await inputs.nth(0).fill(sym);
    await inputs.nth(1).fill('12.50');
    await inputs.nth(2).fill('10');
    await page.locator('div[role="dialog"]').getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.locator('div[role="dialog"]')).toBeHidden({ timeout: 25000 });
    await expect.poll(() => rows().count(), { timeout: 15000 }).toBe(1);

    // Expand the row and remove it; wait for the live list to drop it
    await rows().first().click();
    await page.getByRole('button', { name: 'Remove', exact: true }).first().click();
    await expect.poll(() => rows().count(), { timeout: 25000 }).toBe(0);

    // Reload — the deletion must have persisted
    await page.reload();
    await expect.poll(() => rows().count(), { timeout: 15000 }).toBe(0);
  });
});
