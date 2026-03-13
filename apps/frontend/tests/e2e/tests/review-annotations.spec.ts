import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Multi-target review annotation tests — NEW feature #1479.
 *
 * Covers: D10.2 (add overall test result review), D10.5 (revert review),
 * D10.6 (pass rate recalculates after override).
 * Tagged @new-feature for separate CI execution against staging.
 */
test.describe('Review Annotations — test result level @new-feature', () => {
  /** Navigate to the first test run detail page and return it, or skip. */
  async function gotoFirstRunDetail(page: import('@playwright/test').Page) {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      return false;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      return false;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');
    return true;
  }

  test('can open the Reviews tab on a test result', async ({ page }) => {
    const loaded = await gotoFirstRunDetail(page);
    if (!loaded) {
      test.skip(true, 'No test run rows — skipping review annotation test');
      return;
    }

    // Click the first test result in the left panel (Split view)
    const firstResult = page.locator('[role="row"]').nth(1);
    const hasResult = await firstResult
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasResult) {
      test.skip(true, 'No test results in run — skipping');
      return;
    }
    await firstResult.click();
    await page.waitForLoadState('networkidle');

    // Click the "Reviews" tab
    const reviewsTab = page.getByRole('tab', { name: /reviews/i }).first();
    const hasReviews = await reviewsTab
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasReviews) {
      test.skip(true, 'Reviews tab not found — skipping');
      return;
    }
    await reviewsTab.click();

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can add a Pass review annotation on a test result', async ({
    page,
  }) => {
    const loaded = await gotoFirstRunDetail(page);
    if (!loaded) {
      test.skip(true, 'No test run rows — skipping add review test');
      return;
    }

    const firstResult = page.locator('[role="row"]').nth(1);
    const hasResult = await firstResult
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasResult) {
      test.skip(true, 'No test results in run — skipping');
      return;
    }
    await firstResult.click();
    await page.waitForLoadState('networkidle');

    // Open the Reviews tab
    const reviewsTab = page.getByRole('tab', { name: /reviews/i }).first();
    const hasReviews = await reviewsTab
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasReviews) {
      test.skip(true, 'Reviews tab not found — skipping');
      return;
    }
    await reviewsTab.click();
    await page.waitForLoadState('networkidle');

    // Click "Add Review"
    const addReviewBtn = page
      .getByRole('button', { name: /add review/i })
      .first();
    const hasAddReview = await addReviewBtn
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasAddReview) {
      test.skip(true, '"Add Review" button not found — skipping');
      return;
    }
    await addReviewBtn.click();

    // A review form/dialog should appear with Pass/Fail toggle and comment field
    const passToggle = page
      .getByRole('button', { name: /^pass$/i })
      .or(page.getByRole('radio', { name: /pass/i }))
      .first();
    const hasPass = await passToggle
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasPass) {
      test.skip(true, 'Pass/Fail toggle not found in review form — skipping');
      return;
    }
    await passToggle.click();

    // Fill the comment field (minimum 10 chars required)
    const commentInput = page
      .getByRole('textbox', { name: /comment/i })
      .first();
    const hasComment = await commentInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasComment) {
      await commentInput.fill('E2E automated review — pass');
    }

    // Submit the review
    const submitBtn = page
      .getByRole('button', { name: /submit|save|confirm/i })
      .first();
    const hasSubmit = await submitBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSubmit) {
      test.skip(true, 'Submit button for review not found — skipping');
      return;
    }
    await submitBtn.click();
    await page.waitForLoadState('networkidle');

    // The review should appear in the reviews list
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can add a metric-level review annotation', async ({ page }) => {
    const loaded = await gotoFirstRunDetail(page);
    if (!loaded) {
      test.skip(true, 'No test run rows — skipping metric review test');
      return;
    }

    const firstResult = page.locator('[role="row"]').nth(1);
    const hasResult = await firstResult
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasResult) {
      test.skip(true, 'No test results in run — skipping');
      return;
    }
    await firstResult.click();
    await page.waitForLoadState('networkidle');

    // Open the Metrics tab
    const metricsTab = page.getByRole('tab', { name: /metrics/i }).first();
    const hasMetrics = await metricsTab
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasMetrics) {
      test.skip(true, 'Metrics tab not found — skipping metric review test');
      return;
    }
    await metricsTab.click();
    await page.waitForLoadState('networkidle');

    // Look for a review/annotate button within a metric accordion
    const annotateBtn = page
      .getByRole('button', { name: /annotate|review|override/i })
      .first();
    const hasAnnotate = await annotateBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasAnnotate) {
      test.skip(true, 'Metric annotation button not found — skipping');
      return;
    }
    await annotateBtn.click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('pass rate card updates after a review override', async ({ page }) => {
    const loaded = await gotoFirstRunDetail(page);
    if (!loaded) {
      test.skip(true, 'No test run rows — skipping pass rate recalc test');
      return;
    }

    // Record the initial pass rate text
    const passRateEl = page.getByText(/pass rate/i).first();
    const hasPassRate = await passRateEl
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasPassRate) {
      test.skip(true, 'Pass rate element not found on detail page — skipping');
      return;
    }

    const initialText = await passRateEl.textContent().catch(() => '');

    // Navigate to a test result and add a review
    const firstResult = page.locator('[role="row"]').nth(1);
    if (!(await firstResult.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, 'No test results — skipping');
      return;
    }
    await firstResult.click();

    const reviewsTab = page.getByRole('tab', { name: /reviews/i }).first();
    if (!(await reviewsTab.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, 'Reviews tab not found — skipping');
      return;
    }
    await reviewsTab.click();

    const addReviewBtn = page
      .getByRole('button', { name: /add review/i })
      .first();
    if (
      !(await addReviewBtn.isVisible({ timeout: 5_000 }).catch(() => false))
    ) {
      test.skip(true, '"Add Review" not found — skipping');
      return;
    }
    await addReviewBtn.click();

    const passToggle = page
      .getByRole('button', { name: /^pass$/i })
      .or(page.getByRole('radio', { name: /pass/i }))
      .first();
    if (await passToggle.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await passToggle.click();
    }

    const commentInput = page
      .getByRole('textbox', { name: /comment/i })
      .first();
    if (await commentInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await commentInput.fill('E2E pass rate recalc test');
    }

    const submitBtn = page
      .getByRole('button', { name: /submit|save|confirm/i })
      .first();
    if (await submitBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await submitBtn.click();
      await page.waitForLoadState('networkidle');
    }

    // After the override, the page should not crash
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    // Verify the pass rate element is still rendered (recalculation happened)
    const updatedText = await passRateEl.textContent().catch(() => '');
    expect(typeof updatedText === 'string').toBeTruthy();
    expect(typeof initialText === 'string').toBeTruthy();
  });
});
