import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

const FAKE_ANNOUNCEMENTS = [
  { Symbol: 'ACI', Date: '2026-06-29', Announcement_Type: 'Dividend', Details: 'ACI declares 15% cash dividend', Sentiment: 'Positive', Expected_Price_Impact: 'High', Sector: 'Pharma' },
  { Symbol: 'BEXIMCO', Date: '2026-06-28', Announcement_Type: 'AGM', Details: 'BEXIMCO schedules AGM for August', Sentiment: 'Neutral', Expected_Price_Impact: 'Low', Sector: 'Textile' },
];

test.describe('Dashboard announcements widget', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/market/announcements*', route => {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(FAKE_ANNOUNCEMENTS) });
    });
    await ensureAccount(page);
    await page.goto('http://localhost:5173/');
  });

  test('shows a recency-ordered announcements feed', async ({ page }) => {
    await expect(page.getByTestId('announcements-feed')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('ACI declares 15% cash dividend')).toBeVisible();
    await expect(page.getByText('BEXIMCO schedules AGM for August')).toBeVisible();
  });
});
