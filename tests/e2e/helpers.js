// Shared login helper — signs up if first run, logs in otherwise
export const TEST_EMAIL = `e2euser_pw@test.com`;
export const TEST_PASS = 'testpass123';
export const TEST_NAME = 'E2E Playwright User';
export const TEST_PHONE = '01700000098';

export async function loginAs(page, email = TEST_EMAIL, password = TEST_PASS) {
  await page.goto('/login');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/', { timeout: 15000 });
}

export async function ensureAccount(page) {
  // Try signup; if email taken, just login
  try {
    await page.goto('/signup');
    await page.fill('input[type="text"]', TEST_NAME);
    await page.fill('input[type="email"]', TEST_EMAIL);
    await page.fill('input[type="tel"]', TEST_PHONE);
    await page.fill('input[type="password"]', TEST_PASS);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/', { timeout: 15000 });
  } catch {
    await loginAs(page);
  }
}
