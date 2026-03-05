import { test, expect } from '@playwright/test';

test.describe('Tasks @sanity', () => {
  test('tasks page loads without error', async ({ page }) => {
    await page.goto('/tasks');
    await expect(page).toHaveURL(/\/tasks/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('tasks page shows correct heading', async ({ page }) => {
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('heading', { name: /tasks/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('tasks page shows data grid or empty state', async ({ page }) => {
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const emptyState = page.locator('main, [role="main"]').first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasMain = await emptyState.isVisible();

    expect(hasGrid || hasMain).toBeTruthy();
  });

  test('tasks page has a valid page title', async ({ page }) => {
    await page.goto('/tasks');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
