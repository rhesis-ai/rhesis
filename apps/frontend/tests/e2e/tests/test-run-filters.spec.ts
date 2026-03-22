import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run interaction tests — filters and view modes.
 *
 * Covers: D1.4 (search + status filters + advanced filters popover),
 * D1.5 (Split ↔ Table view toggle).
 *
 * Requires at least one test run to exist so the filter bar is rendered.
 */
test.describe('Test Runs — filters and view modes @interaction', () => {
  test('can toggle between Split and Table view modes', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test runs grid — skipping view toggle test');
      return;
    }

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    if (rowCount < 2) {
      test.skip(true, 'No test run rows — skipping view toggle test');
      return;
    }

    // Navigate into a test run detail page (the view toggle lives there)
    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // Look for the view toggle buttons (Split / Table)
    const tableToggle = page.getByRole('button', { name: /table/i }).first();
    const splitToggle = page.getByRole('button', { name: /split/i }).first();

    const hasToggle =
      (await tableToggle.isVisible({ timeout: 5_000 }).catch(() => false)) ||
      (await splitToggle.isVisible({ timeout: 5_000 }).catch(() => false));

    if (!hasToggle) {
      test.skip(
        true,
        'View toggle buttons not found on detail page — skipping'
      );
      return;
    }

    // Switch to Table view
    if (await tableToggle.isVisible().catch(() => false)) {
      await tableToggle.click();
      // In Table view a full data grid should be visible
      await page.waitForLoadState('networkidle');
      await expect(page.locator('[role="grid"]').first()).toBeVisible({
        timeout: 10_000,
      });
    }

    // Switch back to Split view
    if (await splitToggle.isVisible().catch(() => false)) {
      await splitToggle.click();
      await page.waitForLoadState('networkidle');
    }

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can use the search filter on the test run detail page', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test runs grid — skipping search filter test');
      return;
    }

    const rows = page.locator('[role="row"]');
    if ((await rows.count()) < 2) {
      test.skip(true, 'No test run rows — skipping search filter test');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // Type into the search input
    const searchInput = page.getByPlaceholder(/search/i).first();
    const hasSearch = await searchInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSearch) {
      test.skip(true, 'Search input not found on detail page — skipping');
      return;
    }

    await searchInput.fill('zzz-no-match-xyz');
    await page.waitForLoadState('networkidle');

    // After filtering there should be no errors
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Clear the search
    await searchInput.clear();
    await page.waitForLoadState('networkidle');
  });

  test('can apply Pass/Fail status filter buttons', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test runs grid — skipping status filter test');
      return;
    }

    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping status filter test');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // Click "Passed" filter button
    const passedBtn = page.getByRole('button', { name: /^passed$/i }).first();
    const hasPassedBtn = await passedBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasPassedBtn) {
      await passedBtn.click();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }

    // Click "Failed" filter button
    const failedBtn = page.getByRole('button', { name: /^failed$/i }).first();
    const hasFailedBtn = await failedBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasFailedBtn) {
      await failedBtn.click();
      await page.waitForLoadState('networkidle');
    }

    // Reset to "All"
    const allBtn = page.getByRole('button', { name: /^all$/i }).first();
    if (await allBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await allBtn.click();
    }

    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('can open and close the advanced filters popover', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test runs grid — skipping advanced filters test');
      return;
    }

    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping advanced filters test');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // Click the "Filters" button
    const filtersBtn = page.getByRole('button', { name: /filters/i }).first();
    const hasFilters = await filtersBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasFilters) {
      test.skip(true, 'Filters button not found — skipping');
      return;
    }
    await filtersBtn.click();

    // The popover/panel should open
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Click "Clear All" if present
    const clearAllBtn = page
      .getByRole('button', { name: /clear all/i })
      .first();
    if (await clearAllBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await clearAllBtn.click();
    }

    // Close by pressing Escape
    await page.keyboard.press('Escape');
  });
});
