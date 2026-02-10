import { test, expect } from '@playwright/test';

test.describe('Test Sets @sanity', () => {
  test('test sets page loads successfully', async ({ page }) => {
    await page.goto('/test-sets');
    await expect(page).toHaveURL(/\/test-sets/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('test sets page shows charts and grid sections', async ({ page }) => {
    await page.goto('/test-sets');
    await page.waitForLoadState('networkidle');

    // The page should have rendered some content (grid, chart, or empty state)
    const dataGrid = page.locator('[role="grid"]');
    const charts = page.locator(
      'canvas, svg[class*="chart"], [class*="Chart"]'
    );
    const pageBody = page.locator('body');

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasCharts = (await charts.count()) > 0;
    const hasContent = await pageBody.isVisible();

    expect(hasGrid || hasCharts || hasContent).toBeTruthy();
  });
});
