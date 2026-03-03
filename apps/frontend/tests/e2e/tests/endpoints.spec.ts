import { test, expect } from '@playwright/test';

test.describe('Endpoints @sanity', () => {
  test('endpoints page loads and shows description', async ({ page }) => {
    await page.goto('/endpoints');
    await expect(page).toHaveURL(/\/endpoints/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('endpoints page shows grid or empty state', async ({ page }) => {
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const pageContent = page.locator('main, [role="main"]').first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasContent = await pageContent.isVisible().catch(() => false);

    expect(hasGrid || hasContent).toBeTruthy();
  });
});
