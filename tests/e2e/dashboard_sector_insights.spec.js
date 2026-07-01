import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard sector insights widget', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/');
  });

  test('shows a Sector PE chart by default', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Sector PE' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('sector-insights-chart')).toBeVisible({ timeout: 15000 });
  });

  test('switching tabs swaps between PE, Trade Value, and Gainer/Loser charts', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Sector PE' })).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: 'Trade Value' }).click();
    await expect(page.getByTestId('sector-insights-chart')).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: 'Gainer / Loser' }).click();
    await expect(page.getByTestId('sector-insights-chart')).toBeVisible({ timeout: 15000 });
  });
});
