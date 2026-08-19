import { test, expect } from '@playwright/test';

test('rejecting a queued memory removes it from the review queue', async ({ page }) => {
  await page.goto('/');
  const reject = page.locator('#queue button[data-action="reject"]').first();
  await expect(reject).toBeVisible();
  const id = await reject.getAttribute('data-id');
  expect(id).toBeTruthy();

  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes(`/api/memories/${id}/reject`) && r.request().method() === 'POST',
    ),
    reject.click(),
  ]);
  expect(resp.ok()).toBeTruthy();

  await expect(page.locator(`#queue button[data-action="reject"][data-id="${id}"]`)).toHaveCount(0);
});
