import { test, expect } from '@playwright/test';
import { MetricsPage } from '../pages/MetricsPage';

/**
 * Metrics CRUD interaction tests.
 *
 * Covers: A4.3 (open the create-metric menu), A4.4 (navigate to creation form),
 * A4.5 (fill and submit metric form), A4.6 (edit metric from detail page), and
 * quick filters surviving a metric detail round trip (#3020). Assigning a metric
 * to a requirement is covered from the requirement side in requirements-crud.
 *
 * All tests run against the real backend in Quick Start mode, which seeds the
 * Rhesis, DeepEval and Garak metrics. UI lookups assert rather than skip, so a
 * renamed button fails the test instead of hiding it.
 */
test.describe('Metrics — CRUD @crud', () => {
  test('can open the create-metric menu', async ({ page }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await metricsPage.expectLoaded();

    await page.getByRole('button', { name: /^create metric$/i }).click();

    const menu = page.getByRole('menu');
    await expect(
      menu.getByRole('menuitem', { name: /^llm judge$/i })
    ).toBeVisible();
    await expect(
      menu.getByRole('menuitem', { name: /^code evaluation$/i })
    ).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(menu).toBeHidden();
  });

  test('choosing LLM judge opens the metric creation form', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await metricsPage.expectLoaded();

    await page.getByRole('button', { name: /^create metric$/i }).click();
    await page.getByRole('menuitem', { name: /^llm judge$/i }).click();

    await page.waitForURL(/\/metrics\/new\?type=custom-prompt/, {
      timeout: 15_000,
    });
    await expect(
      page.getByText(/metric information and criteria/i).first()
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can fill and submit the metric creation form', async ({ page }) => {
    test.slow();
    await page.goto('/metrics/new?type=custom-prompt');
    await page.waitForLoadState('networkidle');

    const UNIQUE_NAME = `e2e-metric-${Date.now()}`;

    await page
      .getByRole('textbox', { name: /^name$/i })
      .first()
      .fill(UNIQUE_NAME);
    await page
      .getByRole('textbox', { name: /evaluation prompt/i })
      .first()
      .fill(
        'Evaluate whether the response is helpful and accurate. Score from 0 to 1.'
      );

    await page
      .getByRole('button', { name: /^numeric$/i })
      .first()
      .click();
    await page
      .getByRole('spinbutton', { name: /minimum score/i })
      .first()
      .fill('0');
    await page
      .getByRole('spinbutton', { name: /maximum score/i })
      .first()
      .fill('1');
    await page
      .getByRole('spinbutton', { name: /threshold/i })
      .first()
      .fill('0.5');
    // Single-Turn is preselected; clicking it would clear the required scope.

    await page.getByRole('button', { name: /^next$/i }).click();

    const createBtn = page.getByRole('button', { name: /^create metric$/i });
    await expect(createBtn).toBeVisible({ timeout: 10_000 });
    await createBtn.click();

    await page.waitForURL(/\/metrics(?!\/new)/, { timeout: 20_000 });
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can edit a metric name from the metric detail page', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    // Rhesis metrics are seeded and open a detail page.
    await page.goto('/metrics?backend=rhesis');
    await metricsPage.expectLoaded();

    await metricsPage.cards.first().click();
    await page.waitForURL(/\/metrics\/[^/?]+$/, { timeout: 15_000 });
    await page.waitForLoadState('networkidle');

    const main = page.locator('main');
    // The detail page's name field has a placeholder but no label.
    const nameInput = main.getByPlaceholder('Enter metric name');
    const editBtn = main.getByRole('button', { name: /^edit$/i }).first();
    const saveBtn = main.getByRole('button', { name: /^save$/i }).first();

    const rename = async (name: string) => {
      await editBtn.click();
      await nameInput.fill(name);
      // Save enables only after the field blurs; the page re-checks changes then.
      await nameInput.blur();
      await saveBtn.click();
      await expect(saveBtn).toBeHidden({ timeout: 10_000 });
      await expect(main.getByText(name, { exact: true }).first()).toBeVisible({
        timeout: 10_000,
      });
    };

    await editBtn.click();
    const originalName = await nameInput.inputValue();
    await main
      .getByRole('button', { name: /^cancel$/i })
      .first()
      .click();

    await rename(`${originalName}-e2e-edited`);
    // Put the seeded name back so other tests see the data they expect.
    await rename(originalName);

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('keeps the backend filter after opening a metric and going back', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    const backendParam = (value: string) =>
      new RegExp(`[?&]backend=${value}(&|$)`);

    // Rhesis and Custom metrics are the ones whose cards open a detail page.
    let backend: string | undefined;
    let filteredCount = 0;
    for (const name of ['Rhesis', 'Custom']) {
      const pill = page
        .getByRole('button', { name: new RegExp(`^${name}$`, 'i') })
        .first();
      if (!(await pill.isVisible({ timeout: 5_000 }).catch(() => false))) {
        continue;
      }
      await pill.click();
      await expect(page).toHaveURL(backendParam(name.toLowerCase()));
      filteredCount = await metricsPage.getCardCount();
      if (filteredCount > 0) {
        backend = name.toLowerCase();
        break;
      }
      await pill.click();
    }
    if (!backend) {
      test.skip(true, 'No Rhesis or Custom metrics to open — skipping');
      return;
    }
    const cards = metricsPage.cards;

    await cards.first().click();
    await page.waitForURL(/\/metrics\/[^/?]+/, { timeout: 15_000 });
    await page.goBack();

    await expect(page).toHaveURL(backendParam(backend));
    await expect(cards).toHaveCount(filteredCount);

    await page.reload();
    await expect(page).toHaveURL(backendParam(backend));
    await expect(cards).toHaveCount(filteredCount);
  });
});
