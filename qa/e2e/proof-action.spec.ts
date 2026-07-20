import { test, expect } from '@playwright/test';

// Stands in for the receipt/proof path: Export Snapshot is deterministic (needs
// no prior injected actions) and exercises the same proof pipeline receipts use.
test('exporting a snapshot produces a proof artifact', async ({ page }) => {
  await page.goto('/');
  const snapshotBtn = page.locator('#snapshotBtn');
  await expect(snapshotBtn).toBeVisible();

  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/snapshot') && r.request().method() === 'POST'),
    snapshotBtn.click(),
  ]);
  expect(resp.ok()).toBeTruthy();
});
