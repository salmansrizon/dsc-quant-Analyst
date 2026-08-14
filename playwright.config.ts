import { defineConfig, devices } from '@playwright/test';

/**
 * E2E config for local full-stack verification (map #109, #113/#114).
 *
 * Boots both servers so `npx playwright test` is self-contained:
 *  - backend  FastAPI on :8000 (real BigQuery via the local service-account key)
 *  - frontend Vite dev on :5173, which proxies /api -> :8000
 * `reuseExistingServer` lets it attach to servers already running in dev.
 *
 * This exercises the app end-to-end against real data locally, standing in for
 * the Vercel deploy until #110's prod secrets are provisioned.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'python3 -m uvicorn backend.api:app --port 8000 --log-level warning',
      url: 'http://localhost:8000/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
