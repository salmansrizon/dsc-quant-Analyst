import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Dashboard market strength widget', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/');
  });

  test('shows a Strength Meter view by default', async ({ page }) => {
    await expect(page.getByTestId('market-strength-widget')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('strength-meter')).toBeVisible({ timeout: 15000 });
  });

  test('toggling to Pie view shows the Winner-Loser pie chart', async ({ page }) => {
    await expect(page.getByTestId('market-strength-widget')).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Pie' }).click();
    await expect(page.getByTestId('strength-pie')).toBeVisible({ timeout: 15000 });
  });
});
