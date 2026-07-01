import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Stock Profile navigation', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/watchlist');
    // Add ABBANK to watchlist if not there
    await page.fill('input[placeholder*="Symbol"]', 'ABBANK');
    await page.getByRole('button', { name: /Add/ }).click();
    await page.waitForTimeout(1500);
  });

  test('clicking a watchlist symbol navigates to its Stock Profile page', async ({ page }) => {
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await expect(symbolBtn).toBeVisible({ timeout: 8000 });
    await symbolBtn.click();
    await expect(page).toHaveURL(/\/stocks\/ABBANK/);
    await expect(page.getByRole('heading', { name: 'ABBANK' })).toBeVisible({ timeout: 8000 });
  });

  test('topbar search navigates to the Stock Profile page for the searched symbol', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('ABBANK');
    await searchInput.press('Enter');
    await expect(page).toHaveURL(/\/stocks\/ABBANK/i);
    await expect(page.getByTestId('stock-price')).toBeVisible({ timeout: 8000 });
  });
});
