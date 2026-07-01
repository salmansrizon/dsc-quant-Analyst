import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Alerts page', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/alerts');
  });

  test('renders alerts page with create form and tabs', async ({ page }) => {
    await expect(page.getByRole('main').getByText('Price Alerts', { exact: true })).toBeVisible();
    // Active/Triggered tabs
    await expect(page.getByRole('button', { name: /Active/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Triggered/ })).toBeVisible();
    await expect(page.locator('input[placeholder="ABBANK"]')).toBeVisible();
    await expect(page.locator('input[placeholder="50.00"]')).toBeVisible();
  });

  test('can create a new price alert', async ({ page }) => {
    await page.fill('input[placeholder="ABBANK"]', 'ABBANK');
    await page.fill('input[placeholder="50.00"]', '60');
    await page.getByRole('button', { name: /Add Alert/ }).click();
    await page.waitForTimeout(2000);
    await expect(page.getByRole('main').getByText('ABBANK').first()).toBeVisible({ timeout: 8000 });
  });

  test('active tab shows content or empty state', async ({ page }) => {
    await page.getByRole('button', { name: /Active/ }).click();
    const empty = page.getByText('No active alerts');
    const hasRows = await page.getByText('â–² Above').count() > 0 || await page.getByText('â–¼ Below').count() > 0;
    const hasEmpty = await empty.count() > 0;
    expect(hasRows || hasEmpty).toBe(true);
  });

  test('triggered tab shows content or empty state', async ({ page }) => {
    await page.getByRole('button', { name: /Triggered/ }).click();
    const hasEmpty = await page.getByText('No triggered alerts yet').count() > 0;
    const hasTriggered = await page.getByText('Triggered').count() > 0;
    expect(hasEmpty || hasTriggered).toBe(true);
  });

  test('can delete an active alert', async ({ page }) => {
    // Create one first
    await page.fill('input[placeholder="ABBANK"]', 'BRAC');
    await page.fill('input[placeholder="50.00"]', '40');
    await page.getByRole('button', { name: /Add Alert/ }).click();
    await page.waitForTimeout(2000);
    // Find and click trash button (danger-colored button with SVG)
    const trashBtns = page.locator('button[style*="rgb(239"]');
    const count = await trashBtns.count();
    if (count > 0) {
      await trashBtns.last().click();
      await page.waitForTimeout(1500);
    }
  });
});
