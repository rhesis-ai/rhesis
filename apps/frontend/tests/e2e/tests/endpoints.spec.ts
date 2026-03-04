import { test, expect } from '@playwright/test';

test.describe('Endpoints @sanity', () => {
  test('endpoints page loads without error', async ({ page }) => {
    await page.goto('/endpoints');
    await expect(page).toHaveURL(/\/endpoints/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('endpoints page shows correct heading', async ({ page }) => {
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('heading', { name: /endpoints/i })
    ).toBeVisible();
  });

  test('endpoints page shows description text', async ({ page }) => {
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/connect the rhesis platform/i)).toBeVisible();
  });

  test('endpoints page shows data grid or empty state', async ({ page }) => {
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const mainContent = page.locator('main, [role="main"]').first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasGrid || hasMain).toBeTruthy();
  });

  test('endpoints page has a valid page title', async ({ page }) => {
    await page.goto('/endpoints');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
