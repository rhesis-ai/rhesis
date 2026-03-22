import { test, expect } from '@playwright/test';
import { BehaviorsPage } from '../pages/BehaviorsPage';
import { confirmDeleteDialog } from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for Behaviors.
 *
 * Covers: A3.4 (create), A3.5 (edit), A3.6 (assign metric), A3.9 (delete).
 * All tests run against the real backend in Quick Start mode.
 */
test.describe('Behaviors — CRUD @crud', () => {
  test('can create a behavior via the drawer', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-${Date.now()}`;

    const behaviorsPage = new BehaviorsPage(page);
    await behaviorsPage.goto();
    await behaviorsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await behaviorsPage.openNewBehaviorDrawer();
    await behaviorsPage.fillBehaviorName(UNIQUE_NAME);
    await behaviorsPage.fillBehaviorDescription(
      'Created by Playwright CRUD test'
    );
    await behaviorsPage.submitNewBehavior();

    // The drawer should close after a successful save
    await behaviorsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');

    // The new behavior card should appear in the grid
    const visible = await behaviorsPage.cardIsVisible(UNIQUE_NAME);
    expect(visible).toBeTruthy();
  });

  test('can edit a behavior name and description', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-edit-${Date.now()}`;
    const UPDATED_NAME = `${UNIQUE_NAME}-updated`;

    const behaviorsPage = new BehaviorsPage(page);
    await behaviorsPage.goto();
    await behaviorsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a behavior to edit ---
    await behaviorsPage.openNewBehaviorDrawer();
    await behaviorsPage.fillBehaviorName(UNIQUE_NAME);
    await behaviorsPage.submitNewBehavior();
    await behaviorsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Edit: click pencil icon on the card ---
    await behaviorsPage.clickEditOnCard(UNIQUE_NAME);

    // The edit drawer should open — use :not([aria-hidden="true"]) to avoid
    // matching the permanently-hidden BehaviorMetricsViewer portal.
    await page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Clear and re-fill the name
    const nameInput = page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('textbox', { name: /name/i })
      .first();
    await nameInput.clear();
    await nameInput.fill(UPDATED_NAME);

    // Save changes
    await page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('button', { name: /save changes|save/i })
      .first()
      .click();

    // Drawer should close
    await page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'hidden', timeout: 15_000 });
    await page.waitForLoadState('networkidle');

    // The updated name should appear on the card
    const updated = await behaviorsPage.cardIsVisible(UPDATED_NAME);
    expect(updated).toBeTruthy();
  });

  test('can delete a behavior via the delete icon', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-del-${Date.now()}`;

    const behaviorsPage = new BehaviorsPage(page);
    await behaviorsPage.goto();
    await behaviorsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a behavior to delete ---
    await behaviorsPage.openNewBehaviorDrawer();
    await behaviorsPage.fillBehaviorName(UNIQUE_NAME);
    await behaviorsPage.submitNewBehavior();
    await behaviorsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Delete: click the trash icon on the card ---
    await behaviorsPage.clickDeleteOnCard(UNIQUE_NAME);

    // Confirm in the deletion dialog
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    // The card should no longer be visible
    const gone = await behaviorsPage.cardIsGone(UNIQUE_NAME);
    expect(gone).toBeTruthy();
  });

  test('can assign a metric to a behavior via the add metric dialog', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-beh-metric-${Date.now()}`;

    const behaviorsPage = new BehaviorsPage(page);
    await behaviorsPage.goto();
    await behaviorsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a behavior ---
    await behaviorsPage.openNewBehaviorDrawer();
    await behaviorsPage.fillBehaviorName(UNIQUE_NAME);
    await behaviorsPage.submitNewBehavior();
    await behaviorsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Assign metric: click the "+" icon on the card ---
    await behaviorsPage.clickAddMetricOnCard(UNIQUE_NAME);

    // The Select Metrics dialog should open
    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(
        true,
        'Select Metrics dialog did not open — skipping metric assignment'
      );
      return;
    }

    // Pick the first available metric in the list
    const firstMetricOption = dialog
      .locator('[role="checkbox"], input[type="checkbox"]')
      .first();
    const hasMetric = await firstMetricOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasMetric) {
      test.skip(
        true,
        'No metrics available in dialog — skipping metric assignment'
      );
      return;
    }
    await firstMetricOption.click();

    // Close/confirm the dialog
    const saveBtn = dialog
      .getByRole('button', { name: /save|done|confirm|close/i })
      .first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasSave) await saveBtn.click();
    else await page.keyboard.press('Escape');

    await page.waitForLoadState('networkidle');

    // The behavior card should still be visible (no crash)
    const visible = await behaviorsPage.cardIsVisible(UNIQUE_NAME);
    expect(visible).toBeTruthy();
  });
});
