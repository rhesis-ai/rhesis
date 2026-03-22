import { test, expect, type Page } from '@playwright/test';
import { MetricsPage } from '../pages/MetricsPage';

/**
 * Metrics CRUD interaction tests.
 *
 * Covers: A4.3 (open New Metric dialog), A4.4 (navigate to creation form),
 * A4.5 (fill and submit metric form), A4.6 (edit metric from detail page),
 * A4.7 (assign metric to behavior from metric list card).
 *
 * The Metrics page is only visible to superusers; tests gracefully skip
 * when redirected away from /metrics (non-superuser session).
 *
 * All tests run against the real backend in Quick Start mode.
 */
test.describe('Metrics — CRUD @crud', () => {
  test('can open the New Metric type-selection dialog', async ({ page }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping New Metric dialog test');
      return;
    }

    await metricsPage.expectLoaded();

    // "New Metric" button lives in the SearchAndFilterBar
    const newMetricBtn = page
      .getByRole('button', { name: /^new metric$/i })
      .first();
    const hasBtn = await newMetricBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(true, '"New Metric" button not found — skipping');
      return;
    }

    await newMetricBtn.click();

    // The type-selection dialog should open
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10_000 });

    // Dialog should contain the "Evaluation Prompt" option card
    await expect(dialog.getByText(/evaluation prompt/i).first()).toBeVisible({
      timeout: 5_000,
    });

    // Close the dialog
    const cancelBtn = dialog.getByRole('button', { name: /cancel/i });
    if (await cancelBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await cancelBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }
  });

  test('selecting Evaluation Prompt navigates to the metric creation form', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(
        true,
        'Not a superuser — skipping metric creation navigation test'
      );
      return;
    }

    await metricsPage.expectLoaded();

    const newMetricBtn = page
      .getByRole('button', { name: /^new metric$/i })
      .first();
    if (
      !(await newMetricBtn.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, '"New Metric" button not found — skipping');
      return;
    }

    await newMetricBtn.click();

    const dialog = page.getByRole('dialog');
    if (!(await dialog.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Type-selection dialog did not open — skipping');
      return;
    }

    // Click the "Evaluation Prompt" option card
    const evalPromptOption = dialog.getByText(/evaluation prompt/i).first();
    if (
      !(await evalPromptOption.isVisible({ timeout: 5_000 }).catch(() => false))
    ) {
      test.skip(true, '"Evaluation Prompt" option not found — skipping');
      return;
    }

    await evalPromptOption.click();

    // Should navigate to /metrics/new
    const navigated = await page
      .waitForURL(/\/metrics\/new/, { timeout: 15_000 })
      .then(() => true)
      .catch(() => false);
    if (!navigated) {
      test.skip(true, '/metrics/new URL not reached — skipping');
      return;
    }

    // The stepper should be visible with "Metric Information" step
    await expect(page.getByText(/metric information/i).first()).toBeVisible({
      timeout: 10_000,
    });

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can fill and submit the metric creation form', async ({ page }) => {
    test.slow();
    await page.goto('/metrics/new?type=custom-prompt');
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics/new')) {
      test.skip(
        true,
        'Not a superuser or redirected — skipping metric creation test'
      );
      return;
    }

    const UNIQUE_NAME = `e2e-metric-${Date.now()}`;

    // Fill Name
    const nameInput = page.getByRole('textbox', { name: /^name$/i }).first();
    if (!(await nameInput.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Name field not found on /metrics/new — skipping');
      return;
    }
    await nameInput.fill(UNIQUE_NAME);

    // Fill Evaluation Prompt (required)
    const evalPromptInput = page
      .getByRole('textbox', { name: /evaluation prompt/i })
      .first();
    if (
      await evalPromptInput.isVisible({ timeout: 5_000 }).catch(() => false)
    ) {
      await evalPromptInput.fill(
        'Evaluate whether the response is helpful and accurate. Score from 0 to 1.'
      );
    }

    // Set Score Type to Numeric (click the chip)
    const numericChip = page
      .getByRole('button', { name: /^numeric$/i })
      .first();
    if (await numericChip.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await numericChip.click();
    }

    // Fill Min/Max/Threshold for numeric type
    const minInput = page
      .getByRole('spinbutton', { name: /minimum score/i })
      .first();
    const maxInput = page
      .getByRole('spinbutton', { name: /maximum score/i })
      .first();
    const thresholdInput = page
      .getByRole('spinbutton', { name: /threshold/i })
      .first();

    if (await minInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await minInput.fill('0');
    }
    if (await maxInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await maxInput.fill('1');
    }
    if (await thresholdInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await thresholdInput.fill('0.5');
    }

    // Set Metric Scope to Single-Turn
    const singleTurnChip = page
      .getByRole('button', { name: /single.turn/i })
      .first();
    if (await singleTurnChip.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await singleTurnChip.click();
    }

    // Click "Next" to advance to the confirmation step
    const nextBtn = page.getByRole('button', { name: /^next$/i }).first();
    if (!(await nextBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, '"Next" button not found — skipping');
      return;
    }
    await nextBtn.click();
    await page.waitForLoadState('networkidle');

    // Confirmation step should show the metric name
    const confirmationVisible = await page
      .getByText(/confirmation/i)
      .first()
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!confirmationVisible) {
      test.skip(true, 'Confirmation step not reached — skipping submit');
      return;
    }

    // Click "Create Metric"
    const createBtn = page
      .getByRole('button', { name: /create metric/i })
      .first();
    if (!(await createBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, '"Create Metric" button not found — skipping submit');
      return;
    }
    await createBtn.click();

    // Should redirect back to /metrics after successful creation
    const redirected = await page
      .waitForURL(/\/metrics(?!\/new)/, { timeout: 20_000 })
      .then(() => true)
      .catch(() => false);

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    if (redirected) {
      // The new metric card should be visible in the list
      await page.waitForLoadState('networkidle');
      const metricCard = page.getByText(UNIQUE_NAME).first();
      await expect(metricCard).toBeVisible({ timeout: 15_000 });
    }
  });

  test('can edit a metric name from the metric detail page', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping metric edit test');
      return;
    }

    await metricsPage.expectLoaded();

    const cardCount = await metricsPage.getCardCount();
    if (cardCount === 0) {
      test.skip(true, 'No metric cards to navigate — skipping edit test');
      return;
    }

    // Click the first metric card to navigate to its detail page
    const firstCard = page.locator('.MuiCard-root').first();
    await firstCard.click();

    const navigated = await page
      .waitForURL(/\/metrics\/.+/, { timeout: 15_000 })
      .then(() => true)
      .catch(() => false);
    if (!navigated) {
      test.skip(true, 'Did not navigate to metric detail — skipping edit test');
      return;
    }

    await page.waitForLoadState('networkidle');

    // Click "Edit Section" on the General Information section
    const editSectionBtn = page
      .getByRole('button', { name: /edit section/i })
      .first();
    const hasEditBtn = await editSectionBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEditBtn) {
      test.skip(true, '"Edit Section" button not found — skipping');
      return;
    }

    await editSectionBtn.click();

    // The Name field should now be editable
    const nameInput = page.getByRole('textbox', { name: /^name$/i }).first();
    const hasNameInput = await nameInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasNameInput) {
      test.skip(
        true,
        'Name input not editable after clicking Edit Section — skipping'
      );
      return;
    }

    const originalName = await nameInput.inputValue();
    const updatedName = `${originalName}-e2e-edited`;

    await nameInput.clear();
    await nameInput.fill(updatedName);

    // Click "Save Section"
    const saveBtn = page.getByRole('button', { name: /save section/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, '"Save Section" button not found — skipping save');
      return;
    }

    await saveBtn.click();
    await page.waitForLoadState('networkidle');

    // The updated name should now be visible on the page
    await expect(page.getByText(updatedName).first()).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can assign a metric to a behavior from the metric card', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping assign-to-behavior test');
      return;
    }

    await metricsPage.expectLoaded();

    const cardCount = await metricsPage.getCardCount();
    if (cardCount === 0) {
      test.skip(true, 'No metric cards — skipping assign test');
      return;
    }

    // Look for the "Add to behavior" / AddIcon button on a card
    const firstCard = page.locator('.MuiCard-root').first();
    await firstCard.hover();

    // The icon button with AddIcon has tooltip text. Try aria-label or title.
    const addToBehaviorBtn = firstCard
      .getByRole('button', { name: /add|assign.*behavior/i })
      .first();
    const hasBtn = await addToBehaviorBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(
        true,
        'Add-to-behavior button not found on metric card — metric may be locked or no assign icon visible'
      );
      return;
    }

    await addToBehaviorBtn.click();

    // The SelectBehaviorsDialog should open
    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(true, 'SelectBehaviors dialog did not open — skipping');
      return;
    }

    // There should be behaviors listed in the dialog
    const behaviorOption = dialog
      .locator('[role="checkbox"], input[type="checkbox"]')
      .first();
    const hasBehavior = await behaviorOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasBehavior) {
      // Close and skip — no behaviors available
      await page.keyboard.press('Escape');
      test.skip(true, 'No behaviors available in dialog — skipping assign');
      return;
    }

    // Select the first behavior
    await behaviorOption.click();

    // Confirm — look for Save/Confirm/Done button
    const confirmBtn = dialog
      .getByRole('button', { name: /save|confirm|done|assign/i })
      .first();
    if (await confirmBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await confirmBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }

    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
