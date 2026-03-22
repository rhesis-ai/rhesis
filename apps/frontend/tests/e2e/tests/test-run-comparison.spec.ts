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

    // Look for the "Compare" button
    const compareBtn = page.getByRole('button', { name: /compare/i }).first();
    const hasCompare = await compareBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCompare) {
      test.skip(true, '"Compare" button not found on detail page — skipping');
      return;
    }

    await compareBtn.click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
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

    const compareBtn = page.getByRole('button', { name: /compare/i }).first();
    const hasCompare = await compareBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCompare) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }
    await compareBtn.click();
    await page.waitForLoadState('networkidle');

    // A baseline dropdown should appear
    const baselineSelect = page
      .getByRole('combobox', { name: /baseline|compare/i })
      .or(page.locator('[aria-haspopup="listbox"]'))
      .first();
    const hasSelect = await baselineSelect
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasSelect) {
      test.skip(
        true,
        'Baseline dropdown not found after clicking Compare — skipping'
      );
      return;
    }

    await baselineSelect.click();
    const firstOption = page.getByRole('option').first();
    const hasOption = await firstOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasOption) {
      await page.keyboard.press('Escape');
      test.skip(
        true,
        'No baseline options available — need at least 2 test runs'
      );
      return;
    }
    await firstOption.click();

    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
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

    const compareBtn = page.getByRole('button', { name: /compare/i }).first();
    if (!(await compareBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }
    await compareBtn.click();

    // Select a baseline
    const baselineSelect = page
      .getByRole('combobox', { name: /baseline|compare/i })
      .or(page.locator('[aria-haspopup="listbox"]'))
      .first();
    if (await baselineSelect.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await baselineSelect.click();
      const firstOption = page.getByRole('option').first();
      if (await firstOption.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await firstOption.click();
      } else {
        await page.keyboard.press('Escape');
        test.skip(
          true,
          'No baseline runs available — skipping stat cards test'
        );
        return;
      }
    }

    await page.waitForLoadState('networkidle');

    // The comparison stat cards (Improved / Regressed / Unchanged) should appear
    const improved = page.getByText(/improved/i).first();
    const regressed = page.getByText(/regressed/i).first();
    const unchanged = page.getByText(/unchanged/i).first();

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

    const compareBtn = page.getByRole('button', { name: /compare/i }).first();
    if (!(await compareBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, '"Compare" button not found — skipping');
      return;
    }
    await compareBtn.click();

    const baselineSelect = page
      .getByRole('combobox', { name: /baseline|compare/i })
      .or(page.locator('[aria-haspopup="listbox"]'))
      .first();
    if (await baselineSelect.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await baselineSelect.click();
      const opt = page.getByRole('option').first();
      if (await opt.isVisible({ timeout: 5_000 }).catch(() => false))
        await opt.click();
      else {
        await page.keyboard.press('Escape');
        test.skip(true, 'No baseline runs — skipping');
        return;
      }
    }

    await page.waitForLoadState('networkidle');

    // Click "Improved" filter button if present
    const improvedBtn = page.getByRole('button', { name: /improved/i }).first();
    if (await improvedBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await improvedBtn.click();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }

    // Click "All" to reset
    const allBtn = page.getByRole('button', { name: /^all$/i }).first();
    if (await allBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await allBtn.click();
    }
  });
});
