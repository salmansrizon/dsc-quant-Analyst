import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173';
const useVercel = BASE_URL.startsWith('https://');

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: { timeout: 12000 },
  fullyParallel: false,
  retries: 1,
  reporter: 'list',
  use: {
    baseURL: BASE_URL,
    headless: true,
    viewport: { width: 1280, height: 800 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  ...(useVercel ? {} : {
    webServer: [
      {
        command: 'npm run dev -- --port 5173',
        url: 'http://localhost:5173',
        reuseExistingServer: true,
        timeout: 20000,
      },
    ],
  }),
});
