import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Interaction tests for the Test Runs feature.
 *
 * Creating a test run requires backend execution, so this suite focuses on
 * navigation and detail-page rendering. If no test runs exist in the
 * Quick-Start environment, each test gracefully skips.
 */
test.describe('Test Runs — navigation @crud', () => {
  test('list page loads without errors', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
  });

  test('clicking a row navigates to the detail page', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(
        true,
        'No test-runs grid rendered — skipping detail navigation'
      );
      return;
    }

    // Check there is at least one data row (not just the header row)
    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    if (rowCount < 2) {
      test.skip(
        true,
        'No test run rows available — skipping detail navigation'
      );
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();

    // Verify the detail page renders core summary sections
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('detail page renders summary cards', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(
        true,
        'No test-runs grid rendered — skipping detail assertions'
      );
      return;
    }

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    if (rowCount < 2) {
      test.skip(
        true,
        'No test run rows available — skipping detail assertions'
      );
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // The detail header should show key summary metrics
    await expect(page.getByText(/pass rate/i).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/tests executed/i).first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test('can click through all detail panel tabs', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test-runs grid rendered — skipping tab navigation');
      return;
    }

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    if (rowCount < 2) {
      test.skip(true, 'No test run rows available — skipping tab navigation');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // The first test result is auto-selected and the tab panel renders
    const tabPanel = page.locator('[role="tabpanel"]').first();

    // Tabs that are always present (Conversation is multi-turn only, so we skip it)
    const alwaysPresentTabs = [
      'Overview',
      'Metrics',
      'Reviews',
      'History',
      'Tasks & Comments',
    ];

    for (const tabName of alwaysPresentTabs) {
      const tab = page.getByRole('tab', { name: new RegExp(tabName, 'i') });

      // If the tab isn't present (e.g. the test run has no results), stop early
      const tabVisible = await tab.isVisible().catch(() => false);
      if (!tabVisible) {
        break;
      }

      await tab.click();

      // Active tab panel should be visible and error-free
      await expect(tabPanel).toBeVisible({ timeout: 10_000 });
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }
  });

  test('can navigate back to the list from the detail page', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();

    const hasGrid = await runsPage.hasDataGrid();
    if (!hasGrid) {
      test.skip(true, 'No test-runs grid rendered — skipping back-navigation');
      return;
    }

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    if (rowCount < 2) {
      test.skip(true, 'No test run rows available — skipping back-navigation');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();

    // Use the browser back button
    await page.goBack();
    await expect(page).toHaveURL(/\/test-runs$/);
  });
});
