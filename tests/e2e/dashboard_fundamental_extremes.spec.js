import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard fundamental extremes widget', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/');
  });

  test('shows a Lowest PE leaderboard by default', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Lowest PE' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('extremes-list')).toBeVisible({ timeout: 15000 });
  });

  test('switching tabs requests the matching extremes metric', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Lowest PE' })).toBeVisible({ timeout: 15000 });

    const navPriceRequest = page.waitForRequest(req => req.url().includes('/api/market/extremes') && req.url().includes('metric=nav_price_high'));
    await page.getByRole('button', { name: 'Highest NAV/Price' }).click();
    await navPriceRequest;
  });
});
