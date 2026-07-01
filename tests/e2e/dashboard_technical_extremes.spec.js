import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard technical extremes widget', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/');
  });

  test('shows a Lowest RSI leaderboard by default', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Lowest RSI' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('technical-extremes-list')).toBeVisible({ timeout: 15000 });
  });

  test('switching tabs requests the matching technical extremes metric', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Lowest RSI' })).toBeVisible({ timeout: 15000 });

    const macdRequest = page.waitForRequest(req => req.url().includes('/api/market/technical-extremes') && req.url().includes('metric=macd_high'));
    await page.getByRole('button', { name: 'Highest MACD' }).click();
    await macdRequest;
  });
});
