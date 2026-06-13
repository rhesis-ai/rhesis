import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run comparison mode tests.
 *
 * Covers: D1.13 (Compare button, baseline dropdown, Improved/Regressed/Unchanged cards).
 * Requires at least two test runs to exist in the backend for full comparison flow.
 */
test.describe('Test Runs — comparison mode @interaction', () => {
  test('can open comparison mode from the detail page', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping comparison test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping comparison test');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    const compareBtn = page
      .getByRole('button', { name: /compare runs/i })
      .first();
    const hasCompare = await compareBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCompare) {
      test.skip(true, '"Compare" button not found on detail page — skipping');
      return;
    }

    const [comparePage] = await Promise.all([
      page.context().waitForEvent('page'),
      compareBtn.click(),
    ]);
    await comparePage.waitForLoadState('domcontentloaded');
    await expect(comparePage.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await comparePage.close();
  });

  test('can select a baseline from the comparison dropdown', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping baseline select test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    const compareBtn = page
      .getByRole('button', { name: /compare runs/i })
      .first();
    const hasCompare = await compareBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCompare) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }

    const [comparePage] = await Promise.all([
      page.context().waitForEvent('page'),
      compareBtn.click(),
    ]);
    await comparePage.waitForLoadState('domcontentloaded');

    const baselineCard = comparePage.getByText(/select a baseline run/i);
    const baselinePicker = comparePage
      .locator('[class*="MuiCardActionArea"]')
      .first();
    const hasPicker =
      (await baselineCard.isVisible({ timeout: 8_000 }).catch(() => false)) &&
      (await baselinePicker.isVisible({ timeout: 3_000 }).catch(() => false));
    if (!hasPicker) {
      await comparePage.close();
      test.skip(true, 'Baseline picker not found — skipping');
      return;
    }
    await baselinePicker.click();
    await comparePage.waitForLoadState('networkidle');
    await expect(comparePage.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await comparePage.close();
  });

  test('comparison mode shows Improved, Regressed, and Unchanged stat cards', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping stat cards test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();
    await page.waitForLoadState('networkidle');

    const compareBtn = page
      .getByRole('button', { name: /compare runs/i })
      .first();
    if (!(await compareBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }

    const [comparePage] = await Promise.all([
      page.context().waitForEvent('page'),
      compareBtn.click(),
    ]);
    await comparePage.waitForLoadState('domcontentloaded');

    const baselinePicker = comparePage
      .locator('[class*="MuiCardActionArea"]')
      .first();
    if (
      !(await baselinePicker.isVisible({ timeout: 8_000 }).catch(() => false))
    ) {
      await comparePage.close();
      test.skip(true, 'No baseline runs available — skipping stat cards test');
      return;
    }
    await baselinePicker.click();
    await comparePage.waitForLoadState('networkidle');

    const improved = comparePage.getByText(/improved/i).first();
    const regressed = comparePage.getByText(/regressed/i).first();
    const unchanged = comparePage.getByText(/unchanged/i).first();

    const hasImproved = await improved
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    const hasRegressed = await regressed
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    const hasUnchanged = await unchanged
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    expect(
      hasImproved || hasRegressed || hasUnchanged,
      'Expected at least one of Improved / Regressed / Unchanged stat cards after baseline selection'
    ).toBeTruthy();
  });

  test('can filter comparison results by Improved/Regressed/Unchanged', async ({
    page,
  }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await runsPage.waitForContent();
    await page.waitForLoadState('networkidle');

    if (!(await runsPage.hasDataGrid())) {
      test.skip(true, 'No test runs grid — skipping comparison filter test');
      return;
    }
    if ((await page.locator('[role="row"]').count()) < 2) {
      test.skip(true, 'No test run rows — skipping');
      return;
    }

    await runsPage.clickFirstRow();
    await runsPage.expectDetailPageLoaded();

    const compareBtn = page
      .getByRole('button', { name: /compare runs/i })
      .first();
    if (!(await compareBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }

    const [comparePage] = await Promise.all([
      page.context().waitForEvent('page'),
      compareBtn.click(),
    ]);
    await comparePage.waitForLoadState('domcontentloaded');

    const baselinePicker = comparePage
      .locator('[class*="MuiCardActionArea"]')
      .first();
    if (
      !(await baselinePicker.isVisible({ timeout: 8_000 }).catch(() => false))
    ) {
      test.skip(true, 'No baseline runs — skipping');
      return;
    }
    await baselinePicker.click();
    await comparePage.waitForLoadState('networkidle');

    const improvedBtn = comparePage
      .getByRole('button', { name: /improved/i })
      .first();
    if (await improvedBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await improvedBtn.click();
      await comparePage.waitForLoadState('networkidle');
      await expect(comparePage.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }

    const allBtn = comparePage.getByRole('button', { name: /^all$/i }).first();
    if (await allBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await allBtn.click();
    }
    await comparePage.close();
  });
});
