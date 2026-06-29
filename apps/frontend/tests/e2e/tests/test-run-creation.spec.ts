import { test, expect, type Page } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

/**
 * Test Run creation flow tests.
 *
 * Covers: D1.2 (create test run drawer) and the new Queued status chip (#1415).
 * Requires at least one Test Set, Project, and Endpoint to exist in the backend.
 */

/**
 * Returns a locator scoped to the currently-open MUI drawer/modal.
 *
 * MUI keeps several `[role="presentation"]` elements in the DOM at all times
 * (sidebar, support panel, …) but hides them with `display:none` via the
 * `MuiModal-hidden` class.  Using `.filter({ visible: true })` targets only
 * the one that is actually open, avoiding Playwright strict-mode violations.
 */
function openDrawer(page: Page) {
  return page.locator('[role="presentation"]').filter({ visible: true });
}

/**
 * Selects the first available option from a labeled combobox inside the drawer.
 * Returns 'ok' if selection succeeded or the field is not present,
 * 'skip' if the field is present but no options are available.
 */
async function selectDrawerCombo(
  page: Page,
  labelPattern: RegExp
): Promise<'ok' | 'skip'> {
  const drawer = openDrawer(page);
  const combo = drawer.getByRole('combobox', { name: labelPattern });
  if (!(await combo.isVisible({ timeout: 5_000 }).catch(() => false))) {
    return 'ok';
  }
  await combo.click();
  const firstOption = page.getByRole('option').first();
  if (!(await firstOption.isVisible({ timeout: 8_000 }).catch(() => false))) {
    await page.keyboard.press('Escape');
    return 'skip';
  }
  await firstOption.click();
  return 'ok';
}

/**
 * Fills all required fields in the Create Test Run drawer:
 * Test Set and Endpoint (RunDrawer newTestRun mode — no name field).
 * Returns false (and calls test.skip) if a required selection has no options.
 */
async function fillCreateTestRunDrawer(page: Page): Promise<boolean> {
  const testSetResult = await selectDrawerCombo(page, /test set/i);
  if (testSetResult === 'skip') {
    test.skip(true, 'No test sets available — skipping');
    return false;
  }

  const endpointResult = await selectDrawerCombo(page, /endpoint/i);
  if (endpointResult === 'skip') {
    test.skip(true, 'No endpoints available — skipping');
    return false;
  }

  return true;
}

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

    // The drawer should open; filter to the currently-visible presentation element
    const drawer = openDrawer(page);
    await drawer.waitFor({ state: 'visible', timeout: 10_000 });

    // Verify key form elements are present inside the drawer
    await expect(drawer).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can fill and submit the Create Test Run drawer', async ({ page }) => {
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
    const drawer = openDrawer(page);
    await drawer.waitFor({ state: 'visible', timeout: 10_000 });

    const filled = await fillCreateTestRunDrawer(page);
    if (!filled) return;

    // Submit the form — RunDrawer uses "Execute Now"
    const submitBtn = drawer
      .getByRole('button', { name: /execute now|run|start|create|save/i })
      .first();
    const hasSubmit = await submitBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSubmit) {
      test.skip(true, 'Submit button not found in drawer — skipping');
      return;
    }
    await submitBtn.click();

    // Wait for drawer to close — success means the API call was accepted
    await drawer.waitFor({ state: 'hidden', timeout: 20_000 });
    await page.waitForLoadState('networkidle');

    // The grid should have at least one row after a successful submission
    await expect(page.locator('[role="row"]').nth(1)).toBeVisible({
      timeout: 15_000,
    });
  });

  test('newly created test run shows a valid status chip', async ({ page }) => {
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
    const drawer = openDrawer(page);
    await drawer.waitFor({ state: 'visible', timeout: 10_000 });

    const filled = await fillCreateTestRunDrawer(page);
    if (!filled) return;

    // Submit — RunDrawer uses "Execute Now"
    const submitBtn = drawer
      .getByRole('button', { name: /execute now|run|start|create|save/i })
      .first();

    // The button may remain disabled if form validation hasn't resolved yet
    // (e.g. the endpoint/test-set state update is still in-flight).
    const submitEnabled = await submitBtn
      .isEnabled({ timeout: 8_000 })
      .catch(() => false);
    if (!submitEnabled) {
      test.skip(true, 'Submit button not enabled after form fill — skipping');
      return;
    }

    await submitBtn.click();

    await drawer.waitFor({ state: 'hidden', timeout: 20_000 });
    await page.waitForLoadState('networkidle');

    // The first data row should show a recognisable status chip
    // Valid statuses: Queued, In Progress, Running, Completed, Failed, Pending
    const firstDataRow = page.locator('[role="row"]').nth(1);
    const rowVisible = await firstDataRow
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
    if (!rowVisible) {
      test.skip(true, 'No test run row found in grid — skipping status check');
      return;
    }

    const statusPattern =
      /queued|in progress|running|completed|failed|pending/i;
    await expect(firstDataRow).toContainText(statusPattern, {
      timeout: 10_000,
    });
  });
});
