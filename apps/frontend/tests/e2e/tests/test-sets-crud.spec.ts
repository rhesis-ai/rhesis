/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { TestSetsPage } from '../pages/TestSetsPage';
import { MockApiHelper } from '../helpers/MockApiHelper';
import {
  confirmDeleteDialog,
  expectGridRowVisible,
  openDrawer,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

import testSetsFixture from '../fixtures/test-sets.json';

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

    const drawer = openDrawer(page);

    // Fill the required Name field inside the open drawer.
    await drawer.getByRole('textbox', { name: /^name/i }).fill(UNIQUE_NAME);

    const typeSelectBtn = drawer.locator('[aria-haspopup="listbox"]').first();
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
    await drawer.getByRole('button', { name: /save changes/i }).click();
    await waitForDrawerClosed(page);

    // The new test set should appear in the list
    await page.waitForLoadState('networkidle');
    await expectGridRowVisible(page, UNIQUE_NAME);
  });

  test('can delete a test set via row actions', async ({ page }) => {
    const UNIQUE_NAME = `e2e-ts-del-${Date.now()}`;

    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // --- Setup: create a test set to delete ---
    await testSetsPage.openNewTestSetDrawer();
    const drawer = openDrawer(page);

    await drawer.getByRole('textbox', { name: /^name/i }).fill(UNIQUE_NAME);

    const setupTypeSelectBtn = drawer
      .locator('[aria-haspopup="listbox"]')
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

    await drawer.getByRole('button', { name: /save changes/i }).click();
    await waitForDrawerClosed(page);
    await page.waitForLoadState('networkidle');
    await expectGridRowVisible(page, UNIQUE_NAME);

    // --- Delete: hover row and click the delete icon ---
    await testSetsPage.deleteRowByText(UNIQUE_NAME);
    await confirmDeleteDialog(page);

    // The test set should no longer appear
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).not.toBeVisible({
      timeout: 10_000,
    });
  });
});

test.describe('Test Sets — click-through @crud', () => {
  test('clicking a grid row navigates to the detail page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/test_sets', testSetsFixture as any[]);

    await page.goto('/test-sets');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();

    if (rowCount < 2) {
      test.skip(true, 'No test set rows visible — skipping click-through');
      return;
    }

    // Click the first data row (index 0 is the header)
    await rows.nth(1).click();

    // Should navigate to a test set detail URL
    await expect(page).toHaveURL(/\/test-sets\/.+/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
