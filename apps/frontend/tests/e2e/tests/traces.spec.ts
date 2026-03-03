import { test, expect } from '@playwright/test';

test.describe('Traces @sanity', () => {
  test('traces page loads successfully', async ({ page }) => {
    await page.goto('/traces');
    await expect(page).toHaveURL(/\/traces/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('traces page shows trace list or empty state', async ({ page }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');

    // Either the "No traces found" empty state or a trace table should appear
    const emptyState = page.getByText(/no traces found/i);
    const traceTable = page.locator('table, [role="grid"]');
    const authRequired = page.getByText(/authentication required/i);

    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasTable = await traceTable.isVisible().catch(() => false);
    const hasAuthMsg = await authRequired.isVisible().catch(() => false);

    // One of these should be present
    expect(hasEmptyState || hasTable || hasAuthMsg).toBeTruthy();
  });
});
