import { test, expect } from '@playwright/test';

test.describe('API Tokens @sanity', () => {
  test('tokens page loads and shows description', async ({ page }) => {
    await page.goto('/tokens');
    await expect(page).toHaveURL(/\/tokens/);

    // Page description should be visible
    await expect(
      page.getByText(/create api tokens to authenticate/i)
    ).toBeVisible();
  });

  test('tokens page shows empty state or token list', async ({ page }) => {
    await page.goto('/tokens');

    // Either the empty state or a data grid should be present
    const emptyState = page.getByText(/no api tokens yet/i);
    const createButton = page.getByRole('button', {
      name: /create api token/i,
    });
    const dataGrid = page.locator('[role="grid"]');

    // Wait for the page to settle (loading completes)
    await page.waitForLoadState('networkidle');

    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasGrid = await dataGrid.isVisible().catch(() => false);

    // One of these should be true
    expect(hasEmptyState || hasGrid).toBeTruthy();

    // The create button should always be available
    await expect(createButton).toBeVisible();
  });
});
