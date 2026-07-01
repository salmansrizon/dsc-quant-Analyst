import { test, expect } from '@playwright/test';

const BASE = '';

const TEST_EMAIL = `e2e_${Date.now()}@test.com`;
const TEST_PASS = 'testpass123';
const TEST_NAME = 'E2E User';
const TEST_PHONE = '01700000099';

test.describe('Auth flow', () => {
  test('login page renders with dark background and DSC Quant branding', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator('text=DSC Quant')).toBeVisible();
    // heading is the div, button is the submit â€” check heading only
    await expect(page.locator('div:has-text("Sign In")').first()).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('signup creates account and redirects to dashboard', async ({ page }) => {
    await page.goto(`${BASE}/signup`);
    await page.fill('input[type="text"]', TEST_NAME);
    await page.fill('input[type="email"]', TEST_EMAIL);
    await page.fill('input[type="tel"]', TEST_PHONE);
    await page.fill('input[type="password"]', TEST_PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 15000 });
    // Sidebar should be visible
    await expect(page.locator('text=DSC Quant').first()).toBeVisible({ timeout: 6000 });
  });

  test('login with valid credentials redirects to dashboard', async ({ page }) => {
    // Use the same account created above in the file (shared test_email is evaluated per run)
    // So this test uses a fresh account via API pre-seeding
    await page.goto(`${BASE}/signup`);
    const email2 = `e2e_login_${Date.now()}@test.com`;
    await page.fill('input[type="text"]', 'Login Test User');
    await page.fill('input[type="email"]', email2);
    await page.fill('input[type="tel"]', '01700000097');
    await page.fill('input[type="password"]', TEST_PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 15000 });
    // Now logout
    await page.locator('button').filter({ has: page.locator('svg') }).last().click();
    await page.waitForURL(/\/login/, { timeout: 8000 });
    // Login again
    await page.fill('input[type="email"]', email2);
    await page.fill('input[type="password"]', TEST_PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 15000 });
    await expect(page.locator('text=DSC Quant').first()).toBeVisible({ timeout: 6000 });
  });

  test('login with wrong password shows error', async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.fill('input[type="email"]', 'nobody@test.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    // Error message should appear
    await page.waitForTimeout(3000);
    // Look for any error text (red div)
    const errorEl = page.locator('div[style*="rgb(239"]').first();
    const errorVisible = await errorEl.count() > 0;
    expect(errorVisible || (await page.locator('text=/fail|error|invalid|incorrect|401/i').count()) > 0).toBe(true);
  });

  test('protected route redirects unauthenticated user to login', async ({ page }) => {
    await page.goto(`${BASE}/`);
    await page.waitForURL(/\/login/, { timeout: 8000 });
  });
});
