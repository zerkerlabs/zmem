import { test, expect } from '@playwright/test';

test('promoting a queued memory removes it from the review queue', async ({ page }) => {
  await page.goto('/');
  const promote = page.locator('#queue button[data-action="promote"]').first();
  await expect(promote).toBeVisible();
  const id = await promote.getAttribute('data-id');
  expect(id).toBeTruthy();

  // Assert at the network level (drift-proof): the promote POST must succeed.
  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes(`/api/memories/${id}/promote`) && r.request().method() === 'POST',
    ),
    promote.click(),
  ]);
  expect(resp.ok()).toBeTruthy();

  // After the reload, that specific memory is no longer promotable in the queue.
  await expect(page.locator(`#queue button[data-action="promote"][data-id="${id}"]`)).toHaveCount(0);
});
