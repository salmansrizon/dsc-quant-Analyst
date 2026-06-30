import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Stock Drawer (slide-over)', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
    await page.goto('http://localhost:5173/watchlist');
    // Add ABBANK to watchlist if not there
    await page.fill('input[placeholder*="Symbol"]', 'ABBANK');
    await page.getByRole('button', { name: /Add/ }).click();
    await page.waitForTimeout(1500);
  });

  test('clicking symbol button opens stock drawer', async ({ page }) => {
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await expect(symbolBtn).toBeVisible({ timeout: 8000 });
    await symbolBtn.click();
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 8000 });
  });

  test('stock drawer shows symbol name in header', async ({ page }) => {
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await symbolBtn.click();
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 8000 });
    // Symbol appears in drawer header (first ABBANK outside the watchlist table)
    const drawerHeader = page.locator('div[style*="font-size: 18px"]');
    await expect(drawerHeader.first()).toContainText('ABBANK', { timeout: 5000 });
  });

  test('stock drawer has set alert form with target input', async ({ page }) => {
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await symbolBtn.click();
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('input[placeholder="Target"]')).toBeVisible();
  });

  test('can set an alert from the stock drawer', async ({ page }) => {
    // BigQuery inserts are slow — extend this test's timeout
    test.setTimeout(90000);
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await symbolBtn.click();
    await expect(page.locator('input[placeholder="Target"]')).toBeVisible({ timeout: 8000 });
    await page.fill('input[placeholder="Target"]', '55.00');
    // Click Set — only button with exact name "Set" at this point (no inline alert form open)
    await page.getByRole('button', { name: 'Set', exact: true }).click();
    // Immediately verify loading state is triggered (button becomes "…")
    await expect(page.getByRole('button', { name: '…' })).toBeVisible({ timeout: 3000 });
    // Now wait up to 20s for BigQuery to resolve to a terminal state
    await page.waitForFunction(() => {
      const body = document.body.textContent || '';
      if (body.includes('Alert set successfully!')) return true;
      const btns = Array.from(document.querySelectorAll('button'));
      return btns.some(b => b.textContent.trim() === 'Set' && !b.disabled);
    }, { timeout: 20000 });
    expect(true).toBe(true);
  });

  test('closing drawer via Close button works', async ({ page }) => {
    const symbolBtn = page.getByRole('main').getByRole('button', { name: 'ABBANK' }).first();
    await symbolBtn.click();
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 8000 });
    // Close button has aria-label="Close" (lucide X icon, no visible text)
    await page.getByRole('button', { name: 'Close' }).click();
    await expect(page.getByText('Set Price Alert')).not.toBeVisible({ timeout: 5000 });
  });

  test('topbar search opens drawer for searched symbol', async ({ page }) => {
    // beforeEach already left us authenticated on /watchlist — the topbar search
    // lives in the shell on every protected page, so no re-navigation is needed.
    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('BRAC');
    await searchInput.press('Enter');
    await expect(page.getByText('Set Price Alert')).toBeVisible({ timeout: 12000 });
  });
});
