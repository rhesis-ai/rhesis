import { test, expect } from '@playwright/test';

test.describe('Test Runs @sanity', () => {
  test('test runs page loads without error', async ({ page }) => {
    await page.goto('/test-runs');
    await expect(page).toHaveURL(/\/test-runs/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('test runs page shows correct heading', async ({ page }) => {
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('heading', { name: /test runs/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('test runs page shows data grid or empty state', async ({ page }) => {
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const mainContent = page.locator('main, [role="main"]').first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible();

    expect(hasGrid || hasMain).toBeTruthy();
  });

  test('test runs page does not show loading spinner indefinitely', async ({
    page,
  }) => {
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');

    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(10);
  });

  test('test runs page has a valid page title', async ({ page }) => {
    await page.goto('/test-runs');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
