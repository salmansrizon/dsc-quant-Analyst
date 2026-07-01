import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Watchlist add-form autocomplete', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/watchlist');
  });

  test('typing in the add field shows symbol suggestions', async ({ page }) => {
    const input = page.locator('input[placeholder*="Symbol"]');
    await expect(input).toBeVisible({ timeout: 10000 });
    await input.fill('brac');
    await expect(page.getByRole('button', { name: /BRACBANK/ })).toBeVisible({ timeout: 8000 });
  });

  test('selecting a suggestion adds it to the watchlist', async ({ page }) => {
    const input = page.locator('input[placeholder*="Symbol"]');
    await expect(input).toBeVisible({ timeout: 10000 });
    await input.fill('bracbank');
    const suggestion = page.getByRole('button', { name: /BRACBANK/ });
    await expect(suggestion).toBeVisible({ timeout: 8000 });
    await suggestion.click();
    // It should appear as a watchlist row button in main
    await expect(page.getByRole('main').getByRole('button', { name: 'BRACBANK' }).first()).toBeVisible({ timeout: 8000 });
  });

  test('inline alert shows a current market price suggestion', async ({ page }) => {
    // Ensure at least one row exists
    const input = page.locator('input[placeholder*="Symbol"]');
    await input.fill('ABBANK');
    await page.getByRole('button', { name: /^Add/ }).click();
    await page.waitForTimeout(1500);
    // Open the inline alert on the first row
    const bell = page.getByRole('button', { name: /Set price alert/ }).first();
    await expect(bell).toBeVisible({ timeout: 8000 });
    await bell.click();
    // The market-price suggestion appears (LTP came from the API)
    await expect(page.getByText(/Current market price à§³/).first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe('Portfolio add-position autocomplete & price suggestion', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('/portfolio');
    await page.waitForTimeout(1000);
    await page.getByRole('button', { name: /Add Position/ }).click();
    await expect(page.getByText('Add Position').first()).toBeVisible({ timeout: 5000 });
  });

  test('typing the symbol shows suggestions inside the modal', async ({ page }) => {
    const modalInput = page.locator('div[role="dialog"] input').first();
    await modalInput.fill('brac');
    await expect(page.getByRole('button', { name: /BRACBANK/ })).toBeVisible({ timeout: 8000 });
  });

  test('selecting a symbol pre-fills the buy price with market price', async ({ page }) => {
    const modalInput = page.locator('div[role="dialog"] input').first();
    await modalInput.fill('bracbank');
    const suggestion = page.getByRole('button', { name: /BRACBANK/ });
    await expect(suggestion).toBeVisible({ timeout: 8000 });
    await suggestion.click();
    // Buy price (2nd input) should now hold a positive number pulled from LTP
    const buyPrice = page.locator('div[role="dialog"] input').nth(1);
    await expect.poll(async () => parseFloat(await buyPrice.inputValue()) || 0, { timeout: 8000 }).toBeGreaterThan(0);
  });

  test('a "use market price" suggestion is offered for the buy price', async ({ page }) => {
    const modalInput = page.locator('div[role="dialog"] input').first();
    await modalInput.fill('ABBANK');
    await expect(page.getByRole('button', { name: /Use market price à§³/ })).toBeVisible({ timeout: 8000 });
  });
});
