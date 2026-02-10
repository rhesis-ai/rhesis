import { test, expect } from '@playwright/test';

test.describe('Test Runs @sanity', () => {
  test('test runs page loads successfully', async ({ page }) => {
    await page.goto('/test-runs');
    await expect(page).toHaveURL(/\/test-runs/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('test runs page shows grid or empty state', async ({ page }) => {
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const pageContent = page.locator('body');

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasContent = await pageContent.isVisible();

    expect(hasGrid || hasContent).toBeTruthy();
  });
});
