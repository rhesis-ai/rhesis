import { test, expect } from '@playwright/test';

test.describe('Traces @sanity', () => {
  test('traces page loads without error', async ({ page }) => {
    await page.goto('/traces');
    await expect(page).toHaveURL(/\/traces/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('traces page shows correct heading', async ({ page }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /traces/i })).toBeVisible();
  });

  test('traces page shows description text', async ({ page }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByText(/view and analyze opentelemetry traces/i)
    ).toBeVisible();
  });

  test('traces page shows trace list, empty state, or auth message', async ({
    page,
  }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');

    const emptyState = page.getByText(/no traces found/i);
    const traceTable = page.locator('table, [role="grid"]');
    const authRequired = page.getByText(/authentication required/i);

    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasTable = await traceTable.isVisible().catch(() => false);
    const hasAuthMsg = await authRequired.isVisible().catch(() => false);

    expect(hasEmptyState || hasTable || hasAuthMsg).toBeTruthy();
  });

  test('traces page has a valid page title', async ({ page }) => {
    await page.goto('/traces');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
