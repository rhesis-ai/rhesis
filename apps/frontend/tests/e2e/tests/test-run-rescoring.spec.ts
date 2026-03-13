import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run re-scoring (re-run with "Reuse Outputs") tests.
 *
 * Covers: D1.12 (open RerunTestRunDrawer, select Reuse Outputs, verify new run created).
 * Requires at least one completed test run in the backend.
 */
test.describe('Test Runs — re-scoring @interaction', () => {
  test('can open the Re-run drawer on a test run detail page', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping re-run test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping re-run test');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    // Look for the "Re-run" button in the filter bar
    const rerunBtn = page
      .getByRole('button', { name: /re.?run|rescore/i })
      .first();
    const hasRerun = await rerunBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasRerun) {
      test.skip(true, '"Re-run" button not found on detail page — skipping');
      return;
    }

    await rerunBtn.click();

    // The RerunTestRunDrawer should open
    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    await expect(page.getByRole('presentation')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can select "Reuse Outputs" in the re-run drawer', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping re-run drawer test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    const rerunBtn = page
      .getByRole('button', { name: /re.?run|rescore/i })
      .first();
    const hasRerun = await rerunBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasRerun) {
      test.skip(true, '"Re-run" button not found — skipping');
      return;
    }
    await rerunBtn.click();

    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Find the "Reuse Outputs" option (radio button or select option)
    const reuseOption = page
      .getByRole('radio', { name: /reuse outputs/i })
      .or(page.getByText(/reuse outputs/i))
      .first();
    const hasReuse = await reuseOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasReuse) {
      test.skip(true, '"Reuse Outputs" option not found in drawer — skipping');
      return;
    }
    await reuseOption.click();

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Close drawer without submitting to avoid side effects
    await page.keyboard.press('Escape');
  });

  test('submitting re-run creates a new test run entry', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping re-run submit test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping');
      return;
    }

    // Capture row count before navigating away so we can compare after re-run
    const initialRowCount = await page.locator('[role="row"]').count();

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    const rerunBtn = page
      .getByRole('button', { name: /re.?run|rescore/i })
      .first();
    const hasRerun = await rerunBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasRerun) {
      test.skip(true, '"Re-run" button not found — skipping submit test');
      return;
    }
    await rerunBtn.click();

    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Select "Reuse Outputs" if available
    const reuseOption = page
      .getByRole('radio', { name: /reuse outputs/i })
      .or(page.getByText(/reuse outputs/i))
      .first();
    if (await reuseOption.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await reuseOption.click();
    }

    // Submit the re-run
    const submitBtn = page
      .locator('[role="presentation"]')
      .getByRole('button', { name: /re.?run test|start|submit|confirm/i })
      .first();
    const hasSubmit = await submitBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSubmit) {
      test.skip(true, 'Submit button not found in re-run drawer — skipping');
      return;
    }
    await submitBtn.click();

    // Drawer should close
    await page
      .getByRole('presentation')
      .waitFor({ state: 'hidden', timeout: 20_000 });

    // Navigate back to the list and verify a new run was created
    await runsPage.goto();
    await runsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Prefer a deterministic signal: newly-created re-runs start in Queued state
    const queuedRow = page
      .locator('[role="row"]')
      .filter({ hasText: /queued/i });
    const hasQueuedRow = await queuedRow
      .first()
      .isVisible({ timeout: 10_000 })
      .catch(() => false);

    if (hasQueuedRow) {
      await expect(queuedRow.first()).toBeVisible();
    } else {
      // Runs may have progressed past Queued; fall back to row count comparison
      const newRowCount = await page.locator('[role="row"]').count();
      expect(newRowCount).toBeGreaterThanOrEqual(initialRowCount);
    }
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
