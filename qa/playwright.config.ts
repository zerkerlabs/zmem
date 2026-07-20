import { defineConfig } from '@playwright/test';

// The dashboard is booted by CI (and locally) before these run. Override with
// ZMEM_DASHBOARD_URL if the port changes.
const baseURL = process.env.ZMEM_DASHBOARD_URL ?? 'http://127.0.0.1:8765';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  // The specs share one dashboard + one SQLite DB (mutable server state), so run
  // them serially — parallel promote/reject would race on the same review queue.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }], ['list']],
  use: { baseURL, trace: 'on-first-retry' },
});
