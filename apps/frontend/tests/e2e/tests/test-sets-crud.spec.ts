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

    // The drawer should show the "New Test Set" heading
    await expect(page.getByText('New Test Set').first()).toBeVisible();

    // Fill the required Name field
    await page.getByLabel('Name').first().fill(UNIQUE_NAME);

    // The Test Set Type select defaults to "Single-Turn" — leave it as-is

    // Save
    await page.getByRole('button', { name: /save/i }).click();

    // Wait for the drawer to close
    await expect(
      page.getByRole('presentation', { name: /new test set/i })
    ).not.toBeVisible({ timeout: 15_000 });

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
    await page.getByLabel('Name').first().fill(UNIQUE_NAME);
    await page.getByRole('button', { name: /save/i }).click();

    // Wait for drawer to close and test set to appear
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
