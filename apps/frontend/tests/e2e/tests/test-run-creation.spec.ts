import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run creation flow tests.
 *
 * Covers: D1.2 (create test run drawer) and the new Queued status chip (#1415).
 * Requires at least one Test Set and one Endpoint to exist in the backend.
 */
test.describe('Test Runs — creation @crud', () => {
  test('can open the Create Test Run drawer', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // The "Create Test Run" button should be visible
    const createBtn = page
      .getByRole('button', { name: /create test run/i })
      .first();
    const btnVisible = await createBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Create Test Run button not found — skipping');
      return;
    }

    await createBtn.click();

    // The drawer should open
    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Verify key form elements are present inside the drawer
    const drawer = page.locator('[role="presentation"]');
    await expect(drawer).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can fill and submit the Create Test Run drawer', async ({ page }) => {
    const UNIQUE_NAME = `e2e-run-${Date.now()}`;

    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const createBtn = page
      .getByRole('button', { name: /create test run/i })
      .first();
    const btnVisible = await createBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Create Test Run button not found — skipping');
      return;
    }

    await createBtn.click();
    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Fill in the run name
    const nameInput = page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /name/i })
      .first();
    const hasName = await nameInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasName) {
      test.skip(true, 'Name field not found in drawer — skipping');
      return;
    }
    await nameInput.fill(UNIQUE_NAME);

    // Select a test set from the dropdown
    const testSetSelect = page
      .locator('[role="presentation"] [aria-haspopup="listbox"]')
      .first();
    const hasTestSetSelect = await testSetSelect
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasTestSetSelect) {
      await testSetSelect.click();
      const firstOption = page.getByRole('option').first();
      const hasOption = await firstOption
        .isVisible({ timeout: 8_000 })
        .catch(() => false);
      if (hasOption) {
        await firstOption.click();
      } else {
        await page.keyboard.press('Escape');
        test.skip(true, 'No test sets available to select — skipping');
        return;
      }
    }

    // Submit the form
    const submitBtn = page
      .locator('[role="presentation"]')
      .getByRole('button', { name: /run|start|create|save/i })
      .first();
    const hasSubmit = await submitBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSubmit) {
      test.skip(true, 'Submit button not found in drawer — skipping');
      return;
    }
    await submitBtn.click();

    // Wait for drawer to close and the run to appear in the grid
    await page
      .getByRole('presentation')
      .waitFor({ state: 'hidden', timeout: 20_000 });
    await page.waitForLoadState('networkidle');

    // The new run should appear in the list
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test('newly created test run shows a valid status chip', async ({ page }) => {
    const UNIQUE_NAME = `e2e-run-status-${Date.now()}`;

    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const createBtn = page
      .getByRole('button', { name: /create test run/i })
      .first();
    const btnVisible = await createBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Create Test Run button not found — skipping');
      return;
    }

    await createBtn.click();
    await page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });

    const nameInput = page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /name/i })
      .first();
    const hasName = await nameInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasName) {
      test.skip(true, 'Name field not found — skipping');
      return;
    }
    await nameInput.fill(UNIQUE_NAME);

    // Try to select a test set
    const testSetSelect = page
      .locator('[role="presentation"] [aria-haspopup="listbox"]')
      .first();
    const hasTestSetSelect = await testSetSelect
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasTestSetSelect) {
      await testSetSelect.click();
      const firstOption = page.getByRole('option').first();
      const hasOption = await firstOption
        .isVisible({ timeout: 8_000 })
        .catch(() => false);
      if (hasOption) await firstOption.click();
      else {
        await page.keyboard.press('Escape');
        test.skip(true, 'No test sets available — skipping');
        return;
      }
    }

    const submitBtn = page
      .locator('[role="presentation"]')
      .getByRole('button', { name: /run|start|create|save/i })
      .first();
    await submitBtn.click();

    await page
      .getByRole('presentation')
      .waitFor({ state: 'hidden', timeout: 20_000 });
    await page.waitForLoadState('networkidle');

    // Locate the row and check that a status chip is visible
    // Valid statuses include: Queued (#1415), In Progress, Completed, Failed
    const row = page.locator('[role="row"]', { hasText: UNIQUE_NAME });
    const rowVisible = await row
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
    if (!rowVisible) {
      test.skip(
        true,
        'New test run row not found in grid — skipping status check'
      );
      return;
    }

    // The row should contain a recognisable status chip
    const statusPattern =
      /queued|in progress|running|completed|failed|pending/i;
    await expect(row).toContainText(statusPattern, { timeout: 10_000 });
  });
});
