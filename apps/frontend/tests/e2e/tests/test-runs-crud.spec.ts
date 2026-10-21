import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';
import { seedCompletedTestRun } from '../helpers/TestRunSeedHelper';

/**
 * Interaction tests for the Test Runs feature.
 *
 * The E2E stack can't execute a run (no worker, no reachable model), so each
 * test seeds a finished run with results through the API and opens it by name.
 */
test.describe('Test Runs — navigation @crud', () => {
  let runName: string;

  test.beforeEach(async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    runName = await seedCompletedTestRun(page);
    await page.reload();
    await runsPage.expectLoaded();
  });

  test('list page loads without errors', async ({ page }) => {
    await expect(
      page.locator('[role="row"]').filter({ hasText: runName })
    ).toBeVisible({ timeout: 15_000 });
  });

  test('clicking a row navigates to the detail page', async ({ page }) => {
    await new TestRunsPage(page).openRun(runName);
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('detail page renders summary cards', async ({ page }) => {
    await new TestRunsPage(page).openRun(runName);

    await expect(page.getByText(/pass rate/i).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText(/tests executed/i).first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test('can click through the detail page and test result tabs', async ({
    page,
  }) => {
    await new TestRunsPage(page).openRun(runName);
    const noServerError = () =>
      expect(page.locator('body')).not.toContainText('Internal Server Error');

    for (const name of [
      'Summary',
      'Tests',
      'Configuration',
      'Traces',
      'Annotations',
    ]) {
      const tab = page.getByRole('tab', { name: new RegExp(`^${name}$`, 'i') });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      await noServerError();
    }

    // Opening a result shows its own tabs in a side panel.
    await page.getByRole('tab', { name: /^tests$/i }).click();
    await page.locator('[role="row"]').nth(1).click();
    for (const name of [
      'Conversation',
      'Evaluation',
      'Annotations',
      'History',
      'Tasks & Comments',
    ]) {
      const tab = page
        .getByRole('tab', { name: new RegExp(`^${name}$`, 'i') })
        .last();
      await tab.click();
      await expect(tab).toHaveAttribute('aria-selected', 'true');
      await noServerError();
    }
  });

  test('can navigate back to the list from the detail page', async ({
    page,
  }) => {
    await new TestRunsPage(page).openRun(runName);
    await page.goBack();
    await expect(page).toHaveURL(/\/test-runs$/);
  });
});
