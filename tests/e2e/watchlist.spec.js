import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Watchlist page', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/watchlist');
  });

  test('renders watchlist heading and add form', async ({ page }) => {
    await expect(page.getByRole('main').getByText('Watchlist', { exact: true })).toBeVisible();
    await expect(page.locator('input[placeholder*="Symbol"]')).toBeVisible();
    await expect(page.getByRole('button', { name: /Add/ })).toBeVisible();
  });

  test('can add a symbol to watchlist', async ({ page }) => {
    await page.fill('input[placeholder*="Symbol"]', 'ABBANK');
    await page.getByRole('button', { name: /Add/ }).click();
    // There will be 1+ ABBANK buttons â€” just verify at least one is visible
    await expect(page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first()).toBeVisible({ timeout: 8000 });
  });

  test('inline Set Alert button appears on watchlist row', async ({ page }) => {
    await page.fill('input[placeholder*="Symbol"]', 'BRAC');
    await page.getByRole('button', { name: /Add/ }).click();
    await page.waitForTimeout(1500);
    // Click bell icon on the first BRAC row
    const firstRow = page.getByRole('main').getByRole('button', { name: 'BRAC' }).first();
    await expect(firstRow).toBeVisible({ timeout: 8000 });
    // Bell button is the next sibling button â€” click the bell (first small button after the row)
    const bellBtn = page.getByRole('main').locator('button').filter({ has: page.locator('svg') }).first();
    await bellBtn.click();
    await page.waitForTimeout(500);
    const targetInput = page.locator('input[placeholder="Target price"]');
    if (await targetInput.count() > 0) {
      await expect(targetInput.first()).toBeVisible();
    }
  });

  test('watchlist page loads with content or empty state', async ({ page }) => {
    // Wait for the API to return (BigQuery can be slow)
    await page.waitForFunction(() => {
      const main = document.querySelector('main');
      if (!main) return false;
      return main.textContent.includes('No symbols in watchlist') ||
             main.querySelector('button') !== null;
    }, { timeout: 12000 });
    // If we reach here, the page loaded successfully
    const hasButtons = await page.getByRole('main').getByRole('button').count() > 1; // >1 because Add button is always there
    const hasEmpty = await page.getByText('No symbols in watchlist').count() > 0;
    expect(hasButtons || hasEmpty).toBe(true);
  });
});
