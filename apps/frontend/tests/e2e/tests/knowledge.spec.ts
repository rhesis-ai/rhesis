import { test, expect } from '@playwright/test';

test.describe('Knowledge @sanity', () => {
  test('knowledge page loads without error', async ({ page }) => {
    await page.goto('/knowledge');
    await expect(page).toHaveURL(/\/knowledge/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('knowledge page shows correct heading', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('heading', { name: /knowledge/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('knowledge page shows description text', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/upload knowledge sources/i)).toBeVisible();
  });

  test('knowledge page shows data grid or empty state', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');

    const dataGrid = page.locator('[role="grid"]');
    const mainContent = page.locator('main, [role="main"]').first();

    const hasGrid = await dataGrid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasGrid || hasMain).toBeTruthy();
  });

  test('knowledge page has a valid page title', async ({ page }) => {
    await page.goto('/knowledge');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
