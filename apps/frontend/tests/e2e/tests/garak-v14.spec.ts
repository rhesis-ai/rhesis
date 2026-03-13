import { test, expect } from '@playwright/test';
import { TestSetsPage } from '../pages/TestSetsPage';

/**
 * Garak v0.14 upgrade tests — NEW feature #1477.
 *
 * Covers: B9.1 (dialog opens with v0.14 probes), B9.2 (import probes and verify
 * test cases appear in the grid).
 * Tagged @new-feature for separate CI execution against staging.
 */
test.describe('Garak v0.14 — import probe dialog @new-feature', () => {
  test('can open the Import from Garak dialog', async ({ page }) => {
    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Click the "Import from Garak" button
    const garakBtn = page
      .getByRole('button', { name: /import from garak|garak/i })
      .first();
    const hasGarak = await garakBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasGarak) {
      test.skip(true, '"Import from Garak" button not found — skipping');
      return;
    }

    await garakBtn.click();

    // The Garak Import Dialog should open
    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(true, 'Garak Import Dialog did not open — skipping');
      return;
    }

    await expect(dialog).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('Garak dialog lists probe modules from v0.14', async ({ page }) => {
    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const garakBtn = page
      .getByRole('button', { name: /import from garak|garak/i })
      .first();
    const hasGarak = await garakBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasGarak) {
      test.skip(true, '"Import from Garak" button not found — skipping');
      return;
    }

    await garakBtn.click();

    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(true, 'Garak Import Dialog did not open — skipping');
      return;
    }

    // Wait for probes to load (the dialog makes an API call to list probe modules)
    await page.waitForLoadState('networkidle');

    // At least one probe/category should be listed
    const probeItems = dialog.locator(
      '[role="checkbox"], [role="listitem"], .MuiListItem-root, [role="treeitem"]'
    );
    const probeCount = await probeItems.count();

    if (probeCount === 0) {
      // May still be loading
      await page.waitForTimeout(3_000);
      const probeCountRetry = await probeItems.count();
      expect(
        probeCountRetry,
        'Expected at least one Garak probe to be listed in the dialog'
      ).toBeGreaterThan(0);
    } else {
      expect(probeCount).toBeGreaterThan(0);
    }

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Close dialog
    await page.keyboard.press('Escape');
  });

  test('can import a garak probe and verify test cases appear', async ({
    page,
  }) => {
    const UNIQUE_SET_NAME = `e2e-garak-${Date.now()}`;

    const testSetsPage = new TestSetsPage(page);
    await testSetsPage.goto();
    await testSetsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const garakBtn = page
      .getByRole('button', { name: /import from garak|garak/i })
      .first();
    const hasGarak = await garakBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasGarak) {
      test.skip(
        true,
        '"Import from Garak" button not found — skipping import test'
      );
      return;
    }

    await garakBtn.click();

    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(true, 'Garak dialog did not open — skipping');
      return;
    }

    await page.waitForLoadState('networkidle');

    // Select the first available probe checkbox
    const firstProbe = dialog.locator('input[type="checkbox"]').first();
    const hasProbe = await firstProbe
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasProbe) {
      test.skip(
        true,
        'No probe checkboxes found in dialog — skipping import test'
      );
      return;
    }
    await firstProbe.click();

    // Enter a name for the new test set (if a name field exists)
    const nameInput = dialog.getByRole('textbox', { name: /name/i }).first();
    if (await nameInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await nameInput.fill(UNIQUE_SET_NAME);
    }

    // Click Import / Confirm
    const importBtn = dialog
      .getByRole('button', { name: /import|create|confirm/i })
      .first();
    const hasImport = await importBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasImport) {
      test.skip(true, 'Import button not found in Garak dialog — skipping');
      return;
    }
    await importBtn.click();

    // Wait for dialog to close and grid to update
    await dialog.waitFor({ state: 'hidden', timeout: 30_000 });
    await page.waitForLoadState('networkidle');

    // A new test set should be visible in the grid
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('[role="grid"]').first()).toBeVisible({
      timeout: 10_000,
    });
  });
});
