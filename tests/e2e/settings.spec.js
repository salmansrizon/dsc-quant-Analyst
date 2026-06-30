import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/settings');
    await page.waitForTimeout(1000);
  });

  test('renders settings page with notification and subscription sections', async ({ page }) => {
    // Page heading is a div inside main
    await expect(page.getByRole('main').getByText('Settings', { exact: true })).toBeVisible();
    await expect(page.getByText('Notification Channels')).toBeVisible();
    await expect(page.getByText('Subscription Package')).toBeVisible();
  });

  test('notification channel toggles are visible', async ({ page }) => {
    // Toggles are <label> elements — use exact match to avoid matching input labels
    await expect(page.locator('label').filter({ hasText: /^telegram$/ })).toBeVisible();
    await expect(page.locator('label').filter({ hasText: /^whatsapp$/ })).toBeVisible();
    await expect(page.locator('label').filter({ hasText: /^email$/ })).toBeVisible();
    await expect(page.locator('label').filter({ hasText: /^web push$/ })).toBeVisible();
  });

  test('save preferences button is visible and clickable', async ({ page }) => {
    const saveBtn = page.getByRole('button', { name: 'Save Preferences' });
    await expect(saveBtn).toBeVisible();
    await saveBtn.click();
    await page.waitForTimeout(1000);
  });

  test('package builder shows delivery channel buttons', async ({ page }) => {
    await expect(page.getByText('Delivery Channels')).toBeVisible();
    // Package builder channel buttons (not the toggle labels)
    await expect(page.getByRole('button', { name: 'telegram' })).toBeVisible();
    // Click to select
    await page.getByRole('button', { name: 'telegram' }).click();
    await page.waitForTimeout(500);
  });

  test('package builder shows price alerts and daily digest toggles', async ({ page }) => {
    await expect(page.getByText('Price Alerts')).toBeVisible();
    await expect(page.getByText('Daily Digest')).toBeVisible();
  });

  test('subscribe button is disabled when no channel selected', async ({ page }) => {
    const subscribeBtn = page.getByRole('button', { name: 'Subscribe & Pay' });
    await expect(subscribeBtn).toBeVisible();
    await expect(subscribeBtn).toBeDisabled();
  });

  test('selecting a channel enables subscribe button', async ({ page }) => {
    await page.getByRole('button', { name: 'telegram' }).click();
    const subscribeBtn = page.getByRole('button', { name: 'Subscribe & Pay' });
    await expect(subscribeBtn).not.toBeDisabled({ timeout: 3000 });
  });

  test('payment modal opens after selecting channel and clicking subscribe', async ({ page }) => {
    await page.getByRole('button', { name: 'telegram' }).click();
    await page.getByRole('button', { name: 'Subscribe & Pay' }).click();
    await expect(page.getByText('Confirm Package')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: 'Proceed to Payment' })).toBeVisible();
  });
});
