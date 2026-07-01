import { test, expect } from '@playwright/test';
import { ensureAccount } from './helpers.js';

test.describe('Stock Profile page', () => {
  test.beforeEach(async ({ page }) => {
    await ensureAccount(page);
  });

  test('navigating to /stocks/:symbol renders symbol and price header', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    await expect(page.getByRole('heading', { name: 'ABBANK' })).toBeVisible({ timeout: 8000 });
    await expect(page.getByTestId('stock-price')).toBeVisible({ timeout: 8000 });
  });

  test('shows fundamentals when the backend returns them', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    await expect(page.getByText('Director Holding %')).toBeVisible({ timeout: 8000 });
  });

  test('unknown symbol shows a graceful not-found state', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/NOTASYMBOL');
    await expect(page.getByText('No data for NOTASYMBOL')).toBeVisible({ timeout: 8000 });
  });

  test('shows a candlestick chart with rendered candles', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    const chart = page.getByTestId('candlestick-chart');
    await expect(chart).toBeVisible({ timeout: 8000 });
    await expect(chart.locator('.candle-body')).not.toHaveCount(0);
  });

  test('shows a volume chart below the candlestick chart', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    await expect(page.getByTestId('volume-chart')).toBeVisible({ timeout: 8000 });
  });

  test('overlays EMA lines on the candlestick chart', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    const chart = page.getByTestId('candlestick-chart');
    await expect(chart).toBeVisible({ timeout: 8000 });
    await expect(chart.locator('.recharts-line-curve')).toHaveCount(4);
  });

  test('shows a bullish/bearish trend summary', async ({ page }) => {
    await page.goto('http://localhost:5173/stocks/ABBANK');
    await expect(page.getByTestId('trend-summary')).toBeVisible({ timeout: 8000 });
  });

  test('setting a price alert from the page creates the alert', async ({ page }) => {
    test.setTimeout(45000); // BigQuery streaming insert for price_alerts can take several seconds
    await page.goto('http://localhost:5173/stocks/ABBANK');
    await page.getByPlaceholder('Target').fill('999');
    await page.getByRole('button', { name: 'Set' }).click();
    await expect(page.getByText('Alert set successfully!')).toBeVisible({ timeout: 30000 });
  });
});
