import { test, expect, type Page } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';
import { seedCompletedTestRun } from '../helpers/TestRunSeedHelper';

/**
 * Multi-target annotation tests.
 *
 * Covers: D10.2 (annotate a test result), D10.6 (pass rate recalculates after
 * override), and opening a metric-level annotation. Each test seeds a finished
 * run (one passed, one failed result) and works on the failed result.
 */

/** Seed a run, open it, and open its failed result in the side panel. */
async function openFailedResult(page: Page) {
  const runsPage = new TestRunsPage(page);
  await runsPage.goto();
  const runName = await seedCompletedTestRun(page);
  await page.reload();
  await runsPage.openRun(runName);
  // Summary is the default tab; the seeded run is one pass, one fail.
  await expect(
    page.getByRole('heading', { name: /^50(\.0)?\s*%$/ })
  ).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole('tab', { name: /^tests$/i }).click();
  await page.locator('[role="row"]').filter({ hasText: 'Failed' }).click();
}

/** Open the result's Annotations tab and save a Pass annotation. */
async function annotateAsPass(page: Page, comment: string) {
  await page
    .getByRole('tab', { name: /^annotations$/i })
    .last()
    .click();
  await page.getByRole('button', { name: /^add annotation$/i }).click();

  await page.getByRole('button', { name: /^pass$/i }).click();
  await page.getByPlaceholder(/explain your verdict/i).fill(comment);
  // Wait for the request itself: the panel can update before it lands, and a
  // reload right after would cancel it.
  const saved = page.waitForResponse(
    r =>
      r.request().method() === 'POST' &&
      r.url().includes('/annotations') &&
      r.ok()
  );
  await page
    .getByRole('button', { name: /^save$/i })
    .last()
    .click();
  await saved;
}

test.describe('Annotations — test result level @crud', () => {
  test('can open the Annotations tab on a test result', async ({ page }) => {
    await openFailedResult(page);

    await page
      .getByRole('tab', { name: /^annotations$/i })
      .last()
      .click();
    await expect(
      page
        .getByRole('tabpanel')
        .last()
        .getByText(/^not annotated$/i)
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: /^add annotation$/i })
    ).toBeVisible();
  });

  test('can add a Pass annotation on a test result', async ({ page }) => {
    await openFailedResult(page);
    await annotateAsPass(page, 'E2E automated annotation — pass');

    await expect(
      page
        .getByRole('tabpanel')
        .last()
        .getByText(/^not annotated$/i)
    ).toBeHidden({ timeout: 10_000 });
    await expect(
      page.getByText('E2E automated annotation — pass').first()
    ).toBeVisible();
  });

  test('can annotate a single metric from the Evaluation tab', async ({
    page,
  }) => {
    await openFailedResult(page);

    await page
      .getByRole('tab', { name: /^evaluation$/i })
      .last()
      .click();
    await page
      .getByRole('button', { name: /^annotate$/i })
      .last()
      .click();

    // Annotating the failed metric preselects Pass and mentions the metric.
    const comment = page.getByPlaceholder(/explain your verdict/i);
    await expect(comment).toContainText('@Answer Fluency');
    const save = page.getByRole('button', { name: /^save$/i }).last();
    await save.click();
    await expect(save).toBeHidden({ timeout: 10_000 });
    await expect(
      page
        .getByRole('tabpanel')
        .last()
        .getByText(/^not annotated$/i)
    ).toBeHidden({ timeout: 10_000 });
  });

  test('pass rate updates after an annotation override', async ({ page }) => {
    await openFailedResult(page);
    await annotateAsPass(page, 'E2E pass rate recalc test');

    // One of two results passed; overriding the failed one makes it two of two.
    // Reloading also shows the new rate was saved, not just updated on screen.
    await page.reload();
    await expect(
      page.getByRole('heading', { name: /^100(\.0)?\s*%$/ })
    ).toBeVisible({
      timeout: 15_000,
    });
  });
});
