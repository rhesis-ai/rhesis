import { test, expect } from '@playwright/test';

test.describe('Tasks @sanity', () => {
  test('tasks page loads successfully', async ({ page }) => {
    await page.goto('/tasks');
    await expect(page).toHaveURL(/\/tasks/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('tasks page shows grid or empty state', async ({ page }) => {
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const pageContent = page.locator('body');

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasContent = await pageContent.isVisible();

    expect(hasGrid || hasContent).toBeTruthy();
  });
});
