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

    // When no traces exist the page renders two "no traces" texts simultaneously:
    // the MUI DataGrid no-rows overlay ("No traces found") and the page-level
    // empty-state card ("No traces yet").  The DataGrid container div
    // ([role="grid"]) is visibility:hidden during that render, so using it as
    // a proxy causes toBeVisible to fail.  Target the first visible text node,
    // an actual data row ([data-rowindex]), or the auth message instead.
    const emptyState = page.getByText(/no traces (found|yet)/i).first();
    const traceRow = page.locator('[data-rowindex]').first();
    const authRequired = page.getByText(/authentication required/i).first();

    await expect(emptyState.or(traceRow).or(authRequired)).toBeVisible({
      timeout: 10_000,
    });
  });

  test('traces page has a valid page title', async ({ page }) => {
    await page.goto('/traces');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
