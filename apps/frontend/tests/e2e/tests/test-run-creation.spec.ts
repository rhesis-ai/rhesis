import { test, expect, type Page } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';
import { openDrawer } from '../helpers/CrudHelper';

/**
 * Test Run creation flow tests.
 *
 * Covers: D1.2 (create test run drawer) and the new Queued status chip (#1415).
 * Quick Start seeds one test set and one endpoint, which is all the drawer needs.
 * UI lookups assert rather than skip: `isVisible({ timeout })` doesn't wait, so
 * the old checks skipped whenever the drawer hadn't finished rendering.
 */

/** Selects the first option of a labeled combobox inside the drawer. */
async function selectDrawerCombo(page: Page, labelPattern: RegExp) {
  const combo = openDrawer(page).getByRole('combobox', { name: labelPattern });
  await combo.click();
  await page.getByRole('option').first().click();
}

/** Opens the Create Test Run drawer and picks the seeded test set and endpoint. */
async function openAndFillCreateTestRunDrawer(page: Page) {
  const runsPage = new TestRunsPage(page);
  await runsPage.goto();
  await runsPage.expectLoaded();

  await page
    .getByRole('button', { name: /^new test run$/i })
    .first()
    .click();
  const drawer = openDrawer(page);
  await expect(drawer).toBeVisible({ timeout: 10_000 });

  await selectDrawerCombo(page, /test set/i);
  await selectDrawerCombo(page, /endpoint/i);

  // Preflight pings the endpoint and model, which E2E can't reach, so it would
  // stop at "Retry". Skipping it is the drawer's own option for that case.
  // The select's label isn't linked to it, so find it through its form control.
  await drawer
    .locator('.MuiFormControl-root')
    .filter({ hasText: 'Run Preflight Checks' })
    .getByRole('combobox')
    .click();
  await page.getByRole('option', { name: /^no\b/i }).click();
  return drawer;
}

test.describe('Test Runs — creation @crud', () => {
  test('can open the Create Test Run drawer', async ({ page }) => {
    const runsPage = new TestRunsPage(page);
    await runsPage.goto();
    await runsPage.expectLoaded();

    await page
      .getByRole('button', { name: /^new test run$/i })
      .first()
      .click();

    const drawer = openDrawer(page);
    await expect(drawer).toBeVisible({ timeout: 10_000 });
    await expect(
      drawer.getByRole('combobox', { name: /test set/i })
    ).toBeVisible();
    await expect(
      drawer.getByRole('combobox', { name: /endpoint/i })
    ).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can fill and submit the Create Test Run drawer', async ({ page }) => {
    const drawer = await openAndFillCreateTestRunDrawer(page);

    const submitBtn = drawer.getByRole('button', { name: /^execute now$/i });
    await expect(submitBtn).toBeEnabled({ timeout: 10_000 });
    await submitBtn.click();

    // The drawer closing means the API accepted the run.
    await expect(drawer).toBeHidden({ timeout: 20_000 });
    await expect(page.locator('[role="row"]').nth(1)).toBeVisible({
      timeout: 15_000,
    });
  });

  test('newly created test run shows a valid status chip', async ({ page }) => {
    const drawer = await openAndFillCreateTestRunDrawer(page);

    const submitBtn = drawer.getByRole('button', { name: /^execute now$/i });
    await expect(submitBtn).toBeEnabled({ timeout: 10_000 });
    await submitBtn.click();
    await expect(drawer).toBeHidden({ timeout: 20_000 });

    // No worker runs in E2E, so the run stays queued; any lifecycle status is valid.
    const firstDataRow = page.locator('[role="row"]').nth(1);
    await expect(firstDataRow).toContainText(
      /queued|in progress|running|completed|failed|pending/i,
      { timeout: 15_000 }
    );
  });
});
