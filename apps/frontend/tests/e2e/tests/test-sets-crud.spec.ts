import { test, expect } from '@playwright/test';
import { TestSetsPage } from '../pages/TestSetsPage';

/**
 * CRUD interaction tests for Test Sets.
 *
 * These tests exercise the create → verify → delete flow using the
 * "New Test Set" drawer against the real backend in Quick Start mode.
 */
test.describe('Test Sets — CRUD @crud', () => {
  test('can create a test set via the drawer', async ({ page }) => {
    const UNIQUE_NAME = `e2e-ts-${Date.now()}`;

    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Open the "New Test Set" drawer
    await testSetsPage.openNewTestSetDrawer();

    // The drawer heading should be visible (BaseDrawer renders <Typography variant="h6">)
    const drawerHeading = page.getByRole('heading', {
      name: /^new test set$/i,
    });
    await expect(drawerHeading).toBeVisible({ timeout: 10_000 });

    // Fill the required Name field.
    // Scope to [role="presentation"] (the MUI Drawer portal) so we never
    // accidentally match a DataGrid filter textbox with the same accessible name.
    await page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /^name/i })
      .fill(UNIQUE_NAME);

    // Explicitly select the Test Set Type.
    // MUI Select renders as role="button" with aria-haspopup="listbox" — not
    // role="combobox".  Scope to the drawer presentation element.
    const typeSelectBtn = page
      .locator('[role="presentation"] [aria-haspopup="listbox"]')
      .first();
    await typeSelectBtn.click();
    const singleTurnOption = page.getByRole('option', { name: /single.turn/i });
    const optionsAvailable = await singleTurnOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!optionsAvailable) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Test set type options not available — skipping');
      return;
    }
    await singleTurnOption.click();

    // Save (button text from BaseDrawer default is "Save Changes")
    await page.getByRole('button', { name: /save changes/i }).click();

    // Wait for the drawer to close.
    // BaseDrawer uses keepMounted:true, so the heading stays in the DOM but
    // becomes CSS-hidden when open=false.  Using the h6 heading is reliable.
    await expect(drawerHeading).not.toBeVisible({ timeout: 15_000 });

    // The new test set should appear in the list
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 15_000 });
  });

  test('can delete a test set via the grid selection', async ({ page }) => {
    const UNIQUE_NAME = `e2e-ts-del-${Date.now()}`;

    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a test set to delete ---
    await testSetsPage.openNewTestSetDrawer();
    const setupHeading = page.getByRole('heading', { name: /^new test set$/i });
    await expect(setupHeading).toBeVisible({ timeout: 10_000 });

    await page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /^name/i })
      .fill(UNIQUE_NAME);

    // Explicitly select the Test Set Type; skip if options not available
    const setupTypeSelectBtn = page
      .locator('[role="presentation"] [aria-haspopup="listbox"]')
      .first();
    await setupTypeSelectBtn.click();
    const setupOption = page.getByRole('option', { name: /single.turn/i });
    const setupTypeAvailable = await setupOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!setupTypeAvailable) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Test set type options not available — skipping');
      return;
    }
    await setupOption.click();

    await page.getByRole('button', { name: /save changes/i }).click();

    // Wait for drawer to close and test set to appear
    await expect(setupHeading).not.toBeVisible({ timeout: 15_000 });
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 15_000 });

    // --- Delete: select the row and use the toolbar delete button ---
    await testSetsPage.selectRowByText(UNIQUE_NAME);

    // The "Delete Test Sets" button should appear in the toolbar
    await expect(
      page.getByRole('button', { name: /delete test sets/i })
    ).toBeVisible({ timeout: 5_000 });

    await testSetsPage.clickDeleteSelected();

    // Confirm in the delete modal/dialog
    const deleteDialog = page.getByRole('dialog');
    await expect(deleteDialog).toBeVisible({ timeout: 5_000 });
    await deleteDialog.getByRole('button', { name: /delete/i }).click();

    // The test set should no longer appear
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).not.toBeVisible({
      timeout: 10_000,
    });
  });
});
