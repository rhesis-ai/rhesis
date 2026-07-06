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

    const emptyState = page.getByText(/no api tokens yet/i);
    const createButton = page.getByRole('button', {
      name: /create api token/i,
    });
    const dataGrid = page.locator('[role="grid"]');

    await expect(emptyState.or(dataGrid)).toBeVisible({ timeout: 15_000 });

    await expect(createButton).toBeVisible();
  });
});
