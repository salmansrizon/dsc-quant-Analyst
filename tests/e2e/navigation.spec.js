import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Navigation & dark UI', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
  });

  test('sidebar renders all nav links', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Watchlist' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Portfolio' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Alerts' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();
  });

  test('dashboard shows stat cards and sector panel', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    // Stat card labels are uppercase divs â€” check at least two are present
    await expect(page.getByText('Total Stocks').first()).toBeVisible();
    await expect(page.getByText('Avg Price').first()).toBeVisible();
    // Sector panel header
    await expect(page.getByText('Sectors').first()).toBeVisible();
  });

  test('can navigate to Watchlist page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Watchlist' }).click();
    await expect(page).toHaveURL(/\/watchlist/);
    // Page heading (span inside the layout)
    await expect(page.getByRole('main').getByText('Watchlist', { exact: true })).toBeVisible();
  });

  test('can navigate to Portfolio page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Portfolio' }).click();
    await expect(page).toHaveURL(/\/portfolio/);
    // The "Positions" heading span
    await expect(page.getByRole('main').getByText('Positions', { exact: true })).toBeVisible();
  });

  test('can navigate to Alerts page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Alerts' }).click();
    await expect(page).toHaveURL(/\/alerts/);
    await expect(page.getByRole('main').getByText('Price Alerts', { exact: true })).toBeVisible();
  });

  test('can navigate to Settings page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.getByRole('main').getByText('Settings', { exact: true })).toBeVisible();
  });

  test('topbar search input is visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
  });

  test('logout button signs out user', async ({ page }) => {
    await page.goto('/');
    // Logout button is the last button with an SVG in topbar
    const logoutBtn = page.locator('header button').last();
    await logoutBtn.click();
    await page.waitForURL(/\/login/, { timeout: 8000 });
  });
});
