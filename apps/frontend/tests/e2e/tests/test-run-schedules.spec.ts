import { test, expect, type Page } from '@playwright/test';

/**
 * Scheduled test runs: create, see on the calendar and list, move one run,
 * pause, open the schedule page, delete.
 *
 * The E2E stack has no Beat or worker, so nothing fires here; the dispatcher
 * has its own backend tests. These cover what a person does in the UI.
 */
test.describe('Test run schedules @crud', () => {
  // Creates through a drawer, then walks several views; first visits compile routes.
  test.slow();

  async function pickFirst(page: Page, label: string) {
    await page.getByRole('combobox', { name: label }).click();
    await page.getByRole('option').first().click();
  }

  async function createSchedule(page: Page, name: string) {
    await page.goto('/test-runs?tab=schedules');
    await page.getByRole('button', { name: 'New schedule' }).first().click();
    await pickFirst(page, 'Test set');
    await pickFirst(page, 'Endpoint');
    await page.getByLabel('Name').fill(name);
    // The preview proves the API accepted the timing before saving.
    await expect(page.getByText('Every weekday at 09:00').first()).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole('button', { name: 'Schedule', exact: true }).click();
    await expect(page.getByText(`Scheduled ${name}`).first()).toBeVisible({
      timeout: 15_000,
    });
  }

  const row = (page: Page, name: string) =>
    page.getByRole('row').filter({ hasText: name });

  async function showList(page: Page) {
    await page.getByRole('button', { name: 'List', exact: true }).click();
  }

  test('can create, pause, open and delete a schedule', async ({ page }) => {
    const name = `e2e-schedule-${Date.now()}`;
    await createSchedule(page, name);

    await showList(page);
    await expect(row(page, name)).toBeVisible({ timeout: 15_000 });
    await expect(row(page, name)).toContainText('Every weekday at 09:00');

    await page.getByRole('button', { name: `Actions for ${name}` }).click();
    await page.getByRole('menuitem', { name: 'Pause' }).click();
    await expect(row(page, name)).toContainText('Paused', { timeout: 15_000 });

    await row(page, name).getByRole('link', { name }).click();
    await page.waitForURL(/\/test-runs\/schedules\/.+/);
    await expect(page.getByRole('heading', { name })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText('Usage so far')).toBeVisible();
    await page.getByRole('tab', { name: 'Configuration' }).click();
    await expect(page.getByText('Run settings')).toBeVisible();

    // Run settings open in the run drawer and save back to the same schedule.
    // .last(): the header's Edit FAB (timing) comes first.
    await page
      .getByRole('button', { name: 'Edit', exact: true })
      .last()
      .click();
    await expect(page.getByText(`Edit ${name}`).first()).toBeVisible();
    const save = page.getByRole('button', { name: 'Save', exact: true });
    await expect(save).toBeEnabled({ timeout: 15_000 });
    await save.click();
    await expect(page.getByText(`Saved ${name}`).first()).toBeVisible({
      timeout: 15_000,
    });

    // The test set banner's link: the Schedules tab shows that test set's schedules only.
    await page.getByRole('tab', { name: 'Summary' }).click();
    const testSetHref = await page
      .locator('main')
      .locator('a[href^="/test-sets/"]')
      .first()
      .getAttribute('href');
    const testSetId = testSetHref?.split('/').pop();
    await page.goto(`/test-runs?tab=schedules&test_set=${testSetId}`);
    await expect(page.getByText(/^Test set: /)).toBeVisible({
      timeout: 15_000,
    });
    await showList(page);
    await expect(row(page, name)).toBeVisible({ timeout: 15_000 });

    await page.goto('/test-runs?tab=schedules');
    await showList(page);
    await page.getByRole('button', { name: `Actions for ${name}` }).click();
    await page.getByRole('menuitem', { name: 'Delete' }).click();
    await page
      .getByRole('dialog', { name: `Delete ${name}?` })
      .getByRole('button', { name: 'Delete' })
      .click();
    await expect(row(page, name)).toHaveCount(0, { timeout: 15_000 });
  });

  test('can move one run with "This run only"', async ({ page }) => {
    const name = `e2e-schedule-move-${Date.now()}`;
    await createSchedule(page, name);

    await page.getByRole('button', { name: 'Week', exact: true }).click();
    // Next week always has weekday runs, whatever day the test runs on.
    await page.getByRole('button', { name: 'Next week' }).click();
    await page
      .getByRole('button', { name: `${name} at 09:00` })
      .first()
      .click();
    await expect(page.getByText(/^This run \(/)).toBeVisible();
    await page.getByLabel('Time').first().fill('10:30');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    const scope = page.getByRole('dialog', { name: /Save changes/ });
    await scope.getByText('This run only').click();
    await scope.getByRole('button', { name: 'Save' }).click();

    await expect(page.getByText(/^This run \(/)).toBeHidden({
      timeout: 15_000,
    });
    await expect(
      page.getByRole('button', { name: `${name} at 10:30` })
    ).toBeVisible({ timeout: 15_000 });
  });

  test('the run drawer offers scheduling without reusing outputs', async ({
    page,
  }) => {
    await page.goto('/test-runs');
    await page.getByRole('button', { name: 'New Test Run' }).first().click();
    await page.getByRole('button', { name: 'More ways to run' }).click();
    await page.getByRole('menuitem', { name: 'Schedule run…' }).click();
    await expect(
      page.getByText('Each run uses the tests in the set').first()
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Reuse Outputs')).toHaveCount(0);
  });
});
