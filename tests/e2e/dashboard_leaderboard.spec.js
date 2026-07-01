import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard leaderboard widget', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/');
  });

  test('shows a Top Value leaderboard by default', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Top Value' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('leaderboard-list')).toBeVisible({ timeout: 15000 });
  });

  test('switching tabs requests the matching leaderboard metric', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Top Value' })).toBeVisible({ timeout: 15000 });

    const gainerRequest = page.waitForRequest(req => req.url().includes('/api/market/leaderboard') && req.url().includes('metric=gainer'));
    await page.getByRole('button', { name: 'Top Gainer' }).click();
    await gainerRequest;

    const loserRequest = page.waitForRequest(req => req.url().includes('/api/market/leaderboard') && req.url().includes('metric=loser'));
    await page.getByRole('button', { name: 'Top Loser' }).click();
    await loserRequest;
  });

  test('shows a last-refreshed indicator near the top of the dashboard', async ({ page }) => {
    await expect(page.getByText(/Market data last refreshed/i)).toBeVisible({ timeout: 15000 });
  });
});
