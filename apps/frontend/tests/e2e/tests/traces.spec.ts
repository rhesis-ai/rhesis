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
    await expect(
      page.getByRole('heading', { name: /traces/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('traces page shows description text', async ({ page }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByText(/opentelemetry traces from test runs/i)
    ).toBeVisible();
  });

  test('traces page shows trace list, empty state, or auth message', async ({
    page,
  }) => {
    await page.goto('/traces');
    await page.waitForLoadState('networkidle');

    // The page settles into one of four states. We target only page-level
    // elements (outside the DataGrid) to avoid the MUI DataGrid NoRowsOverlay
    // h6 ("No traces found") which lives inside a visibility:hidden wrapper
    // when the page-level empty-state card is shown — matching it with a regex
    // would always resolve to the hidden element first (DOM order).
    //
    // State 1: data rows are present
    const traceRow = page.locator('[data-rowindex]').first();
    // State 2: no traces, page-level card (TracesClientWrapper EntityEmptyState)
    const noTracesYet = page.getByText('No traces yet', { exact: true });
    // State 3: no session token (EntityEmptyState in the !sessionToken branch)
    const authRequired = page.getByText('Authentication Required', {
      exact: true,
    });
    // State 4: RBAC gate — canRead is false (AccessDenied component)
    const accessDenied = page.getByText('Access denied', { exact: true });

    await expect(
      traceRow.or(noTracesYet).or(authRequired).or(accessDenied)
    ).toBeVisible({ timeout: 15_000 });
  });

  test('traces page has a valid page title', async ({ page }) => {
    await page.goto('/traces');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
