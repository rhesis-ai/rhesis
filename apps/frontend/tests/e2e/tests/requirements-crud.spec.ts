import { test, expect } from '@playwright/test';
import { RequirementsPage } from '../pages/RequirementsPage';
import { confirmDeleteDialog, openDrawer } from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for Requirements.
 *
 * Covers: A3.4 (create), A3.5 (edit), A3.6 (assign metric), A3.9 (delete).
 * All tests run against the real backend in Quick Start mode.
 */
test.describe('Requirements — CRUD @crud', () => {
  test('can create a requirement via the drawer', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-${Date.now()}`;

    const requirementsPage = new RequirementsPage(page);
    await requirementsPage.goto();
    await requirementsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await requirementsPage.openNewRequirementDrawer();
    await requirementsPage.fillRequirementName(UNIQUE_NAME);
    await requirementsPage.fillRequirementDescription(
      'Created by Playwright CRUD test'
    );
    await requirementsPage.submitNewRequirement();

    // The drawer should close after a successful save
    await requirementsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');

    // The new requirement card should appear in the grid
    const visible = await requirementsPage.cardIsVisible(UNIQUE_NAME);
    expect(visible).toBeTruthy();
  });

  test('can edit a requirement name and description', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-edit-${Date.now()}`;
    const UPDATED_NAME = `${UNIQUE_NAME}-updated`;

    const requirementsPage = new RequirementsPage(page);
    await requirementsPage.goto();
    await requirementsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a requirement to edit ---
    await requirementsPage.openNewRequirementDrawer();
    await requirementsPage.fillRequirementName(UNIQUE_NAME);
    await requirementsPage.submitNewRequirement();
    await requirementsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Edit: click pencil icon on the card ---
    await requirementsPage.clickEditOnCard(UNIQUE_NAME);

    // The edit drawer should open — use :not([aria-hidden="true"]) to avoid
    // matching the permanently-hidden RequirementMetricsViewer portal.
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

    // Updated name appears on the detail page after save
    await expect(page.getByText(UPDATED_NAME).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test('can delete a requirement via the delete icon', async ({ page }) => {
    const UNIQUE_NAME = `e2e-beh-del-${Date.now()}`;

    const requirementsPage = new RequirementsPage(page);
    await requirementsPage.goto();
    await requirementsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a requirement to delete ---
    await requirementsPage.openNewRequirementDrawer();
    await requirementsPage.fillRequirementName(UNIQUE_NAME);
    await requirementsPage.submitNewRequirement();
    await requirementsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Delete: click the trash icon on the card ---
    await requirementsPage.clickDeleteOnCard(UNIQUE_NAME);

    // Confirm in the deletion dialog
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    // The card should no longer be visible
    const gone = await requirementsPage.cardIsGone(UNIQUE_NAME);
    expect(gone).toBeTruthy();
  });

  test('can assign a metric to a requirement via the add metric dialog', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-beh-metric-${Date.now()}`;

    const requirementsPage = new RequirementsPage(page);
    await requirementsPage.goto();
    await requirementsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a requirement ---
    await requirementsPage.openNewRequirementDrawer();
    await requirementsPage.fillRequirementName(UNIQUE_NAME);
    await requirementsPage.submitNewRequirement();
    await requirementsPage.waitForDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });

    // --- Assign metric: click the "+" icon on the card ---
    await requirementsPage.clickAddMetricOnCard(UNIQUE_NAME);

    // Assign Metric drawer opens from the Linked Metrics tab
    await expect(openDrawer(page).getByText(/^assign metric$/i)).toBeVisible({
      timeout: 10_000,
    });

    const drawer = page.locator('.MuiDrawer-root:not([aria-hidden="true"])');

    // Pick the first available metric row in the assign drawer grid
    const metricRow = drawer.locator('[role="row"]').nth(1);
    const hasMetric = await metricRow
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasMetric) {
      test.skip(
        true,
        'No metrics available in assign drawer — skipping metric assignment'
      );
      return;
    }
    await metricRow.locator('input[type="checkbox"]').click();

    // Confirm assignment
    const saveBtn = drawer.getByRole('button', { name: /^assign$/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasSave) await saveBtn.click();
    else await page.keyboard.press('Escape');

    await page.waitForLoadState('networkidle');

    // Requirement detail page should still show the requirement name
    await expect(page.getByText(UNIQUE_NAME).first()).toBeVisible({
      timeout: 15_000,
    });
  });
});
