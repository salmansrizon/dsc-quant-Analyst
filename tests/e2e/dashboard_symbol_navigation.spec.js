import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard symbol-click navigation', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/');
  });

  test('clicking a leaderboard symbol navigates to its Stock Profile page', async ({ page }) => {
    const list = page.getByTestId('leaderboard-list');
    await expect(list).toBeVisible({ timeout: 15000 });

    const firstSymbolBtn = list.getByRole('button').first();
    await expect(firstSymbolBtn).toBeVisible({ timeout: 15000 });
    const symbol = await firstSymbolBtn.innerText();

    await firstSymbolBtn.click();
    await expect(page).toHaveURL(new RegExp(`/stocks/${symbol}`, 'i'));
  });
});
