import { test, expect } from '@playwright/test';

test.describe('Knowledge @sanity', () => {
  test('knowledge page loads and shows description', async ({ page }) => {
    await page.goto('/knowledge');
    await expect(page).toHaveURL(/\/knowledge/);

    // Page description should be visible
    await expect(page.getByText(/upload knowledge sources/i)).toBeVisible();
  });

  test('knowledge page shows sources grid or empty state', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');

    // Either a data grid with sources or the page content should be present
    const dataGrid = page.locator('[role="grid"]');
    const pageContent = page.getByText(/knowledge/i).first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasContent = await pageContent.isVisible().catch(() => false);

    expect(hasGrid || hasContent).toBeTruthy();
  });
});
