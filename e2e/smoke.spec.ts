import { test, expect } from '@playwright/test';

/**
 * UI smoke + auth-gating (#113). No writes — safe to run repeatedly.
 */
test.describe('public UI + auth gating', () => {
  test('login page renders', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('form', { name: 'Login form' })).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
  });

  test('signup page renders', async ({ page }) => {
    await page.goto('/signup');
    await expect(page.getByRole('form', { name: 'Signup form' })).toBeVisible();
    await expect(page.locator('#full_name')).toBeVisible();
    await expect(page.locator('#email')).toBeVisible();
  });

  test('protected route redirects to login when unauthenticated', async ({ page }) => {
    await page.goto('/portfolio');
    await expect(page).toHaveURL(/\/login/);
  });
});
