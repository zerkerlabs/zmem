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

  // Prove an artifact was actually produced — not just a 200. The snapshot
  // export returns a typed, content-addressed artifact.
  const body = await resp.json();
  expect(body.format).toBe('snapshot');
  expect(body.artifact_id).toMatch(/^zmem_snapshot_/);
  expect(body.sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(body.path).toContain('.snapshot.json');
  expect(body.payload?.snapshot_hash).toMatch(/^[0-9a-f]{64}$/);
});
