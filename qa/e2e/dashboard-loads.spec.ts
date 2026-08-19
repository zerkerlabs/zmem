import { test, expect } from '@playwright/test';

test('review console renders its core panels', async ({ page }) => {
  await page.goto('/');
  // Panels are rendered in the static shell; state fills them from /api/state.
  await expect(page.getByText('Proof Inspector', { exact: false })).toBeVisible();
  await expect(page.getByText('Memory In Use', { exact: false })).toBeVisible();
  await expect(page.getByText('Memory Status', { exact: false })).toBeVisible();
  // Seeded queue should surface at least one promotable memory.
  await expect(page.locator('#queue button[data-action="promote"]').first()).toBeVisible();
});
