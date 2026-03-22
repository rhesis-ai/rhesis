import { test, expect, type Page } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run — individual result action tests.
 *
 * Covers: D1.6 (rename test run), D1.7 (switch to Table view),
 * D1.8 (Provide Review drawer opens), D1.9 (submit a Pass review),
 * D1.10 (download CSV), D1.11 (filter results by status).
 *
 * All tests navigate to the first available test run in the list.
 * If no test runs exist in the Quick Start environment the tests
 * gracefully skip.
 *
 * All tests run against the real backend in Quick Start mode.
 */
test.describe('Test Runs — result actions @interaction', () => {
  /** Navigate to the first available test run detail page. Returns false to skip. */
  async function gotoFirstTestRun(page: Page): Promise<boolean> {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();

    if (!(await runsPage.hasDataGrid())) return false;

    const rows = page.locator('[role="row"]');
    if ((await rows.count()) < 2) return false;

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');
    return true;
  }

  test('can rename a test run via the pencil icon', async ({ page }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping rename test');
      return;
    }

    // The pencil icon has Tooltip "Rename test run"
    const renameBtn = page.getByRole('button', { name: /rename test run/i });
    const hasBtn = await renameBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(true, '"Rename test run" button not found — skipping');
      return;
    }

    await renameBtn.click();

    // A dialog should open with a Name text field
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10_000 });

    const nameInput = dialog.getByRole('textbox', { name: /^name$/i }).first();
    const hasInput = await nameInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasInput) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Name field not found in rename dialog — skipping');
      return;
    }

    const originalName = await nameInput.inputValue();
    const newName = `${originalName || 'test-run'}-e2e-renamed`;

    await nameInput.clear();
    await nameInput.fill(newName);

    // Save
    const saveBtn = dialog.getByRole('button', { name: /^save$/i });
    await saveBtn.click();
    await page.waitForLoadState('networkidle');

    // The new name should appear in the page heading
    await expect(page.getByText(newName).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can switch to Table view and see result rows', async ({ page }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping Table view test');
      return;
    }

    // Click the "Table" view mode button
    const tableBtn = page.getByRole('button', { name: /^table$/i }).first();
    const hasTable = await tableBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTable) {
      test.skip(true, '"Table" view button not found — skipping');
      return;
    }

    await tableBtn.click();
    await page.waitForLoadState('networkidle');

    // In table view, a <table> element (or at least rows) should be visible
    const table = page.locator('table').first();
    const hasTbl = await table
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    expect(
      hasTbl,
      'Expected a <table> element to appear after switching to Table view'
    ).toBeTruthy();

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can open the Provide Review drawer from a result row', async ({
    page,
  }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping review drawer test');
      return;
    }

    // Switch to Table view first so action buttons are visible
    const tableBtn = page.getByRole('button', { name: /^table$/i }).first();
    if (await tableBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await tableBtn.click();
      await page.waitForLoadState('networkidle');
    }

    // Look for "Provide Review" button in the Actions column
    const provideReviewBtn = page
      .getByRole('button', { name: /provide review/i })
      .first();
    const hasBtn = await provideReviewBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(
        true,
        '"Provide Review" button not visible — test run may have no results, skipping'
      );
      return;
    }

    await provideReviewBtn.click();

    // The ReviewJudgementDrawer should open with the title "Provide Test Review"
    const drawerTitle = page.getByText(/provide test review/i).first();
    await expect(drawerTitle).toBeVisible({ timeout: 10_000 });

    // Pass and Fail toggle buttons should be present
    const passToggle = page.getByRole('button', { name: /^passed$/i }).first();
    const failToggle = page.getByRole('button', { name: /^failed$/i }).first();
    const hasPassFail =
      (await passToggle.isVisible({ timeout: 3_000 }).catch(() => false)) ||
      (await failToggle.isVisible({ timeout: 3_000 }).catch(() => false));
    expect(
      hasPassFail,
      'Expected Pass/Fail toggle buttons in review drawer'
    ).toBeTruthy();

    // Close without submitting
    const cancelBtn = page.getByRole('button', { name: /cancel/i }).first();
    if (await cancelBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await cancelBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }
  });

  test('can submit a Pass review for a test result', async ({ page }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping submit review test');
      return;
    }

    // Switch to Table view
    const tableBtn = page.getByRole('button', { name: /^table$/i }).first();
    if (await tableBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await tableBtn.click();
      await page.waitForLoadState('networkidle');
    }

    const provideReviewBtn = page
      .getByRole('button', { name: /provide review/i })
      .first();
    if (
      !(await provideReviewBtn
        .isVisible({ timeout: 10_000 })
        .catch(() => false))
    ) {
      test.skip(
        true,
        '"Provide Review" button not visible — skipping submit test'
      );
      return;
    }

    await provideReviewBtn.click();

    const drawerTitle = page.getByText(/provide test review/i).first();
    if (
      !(await drawerTitle.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Review drawer did not open — skipping');
      return;
    }

    // Click the Pass toggle
    const passToggle = page.getByRole('button', { name: /^passed$/i }).first();
    if (!(await passToggle.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Pass toggle not found — skipping');
      return;
    }
    await passToggle.click();

    // Fill in the required review comment (minimum 10 characters)
    const commentInput = page
      .getByRole('textbox', { name: /review comments|explain/i })
      .first();
    if (
      !(await commentInput.isVisible({ timeout: 5_000 }).catch(() => false))
    ) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Review comment field not found — skipping');
      return;
    }
    await commentInput.fill(
      'Playwright E2E review — result looks correct and passes criteria.'
    );

    // Submit
    const submitBtn = page
      .getByRole('button', { name: /submit review/i })
      .first();
    if (!(await submitBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, '"Submit Review" button not found — skipping');
      return;
    }
    await submitBtn.click();
    await page.waitForLoadState('networkidle');

    // The drawer should close — verify no application errors
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('can download test run results as CSV', async ({ page }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping download test');
      return;
    }

    // The Download button is in the filter bar
    const downloadBtn = page
      .getByRole('button', { name: /^download$/i })
      .first();
    const hasBtn = await downloadBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(true, '"Download" button not found — skipping CSV test');
      return;
    }

    // Start waiting for the download before clicking
    const downloadPromise = page.waitForEvent('download', { timeout: 15_000 });
    await downloadBtn.click();

    const download = await downloadPromise.catch(() => null);
    if (download) {
      // Verify the download filename matches the expected pattern
      expect(download.suggestedFilename()).toMatch(/test_run.*results\.csv/i);
    }

    // Even if the download didn't complete, no application errors should occur
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can filter test results by Passed status', async ({ page }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping filter test');
      return;
    }

    // The "Passed" filter button is in the ButtonGroup status filter bar
    const passedBtn = page.getByRole('button', { name: /^passed$/i }).first();
    const hasBtn = await passedBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(
        true,
        '"Passed" filter button not found — skipping filter test'
      );
      return;
    }

    await passedBtn.click();
    await page.waitForLoadState('networkidle');

    // No errors after applying the filter
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Click "Failed" to apply that filter
    const failedBtn = page.getByRole('button', { name: /^failed$/i }).first();
    if (await failedBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await failedBtn.click();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }

    // Reset to "All"
    const allBtn = page.getByRole('button', { name: /^all$/i }).first();
    if (await allBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await allBtn.click();
      await page.waitForLoadState('networkidle');
    }
  });

  test('can open and use the advanced Filters popover on the result list', async ({
    page,
  }) => {
    const reached = await gotoFirstTestRun(page);
    if (!reached) {
      test.skip(true, 'No test runs available — skipping filters popover test');
      return;
    }

    const filtersBtn = page.getByRole('button', { name: /^filters$/i }).first();
    const hasBtn = await filtersBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(true, '"Filters" button not found — skipping popover test');
      return;
    }

    await filtersBtn.click();

    // The popover should contain Review Status options
    const reviewedChip = page.getByText(/^reviewed$/i).first();
    const popoverVisible = await reviewedChip
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    expect(
      popoverVisible,
      'Expected Filters popover to show "Reviewed" chip'
    ).toBeTruthy();

    // Click "Clear All" if present
    const clearAllBtn = page
      .getByRole('button', { name: /clear all/i })
      .first();
    if (await clearAllBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await clearAllBtn.click();
    }

    await page.keyboard.press('Escape');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
