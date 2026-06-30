import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Topbar symbol search autocomplete', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/watchlist');
  });

  test('typing shows a dropdown of matching symbols', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('brac');
    // Debounced lookup (~250ms) then dropdown with BRACBANK
    await expect(page.getByRole('button', { name: /BRACBANK/ })).toBeVisible({ timeout: 8000 });
  });

  test('clicking a suggestion opens the stock drawer', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('brac');
    const suggestion = page.getByRole('button', { name: /BRACBANK/ });
    await expect(suggestion).toBeVisible({ timeout: 8000 });
    await suggestion.click();
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 10000 });
  });

  test('Enter on a matched query opens the first match', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('bracbank');
    await expect(page.getByRole('button', { name: /BRACBANK/ })).toBeVisible({ timeout: 8000 });
    await searchInput.press('Enter');
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 10000 });
  });

  test('unknown query shows a no-matches message', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('zzzzzznotreal');
    await expect(page.getByText(/No matches/)).toBeVisible({ timeout: 8000 });
  });
});
