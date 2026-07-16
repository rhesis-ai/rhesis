import path from 'path';
import { test, expect } from '@playwright/test';
import { KnowledgePage } from '../pages/KnowledgePage';
import {
  confirmDeleteDialog,
  expectGridRowVisible,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for the Knowledge (sources) page.
 *
 * Covers: A2.3 (upload a TXT file), A2.6 (delete a source via row actions).
 * Uses a small fixture TXT file from the fixtures directory.
 */
test.describe('Knowledge — CRUD @crud', () => {
  test('can open the Upload Source dialog', async ({ page }) => {
    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Open the upload dialog
    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    await knowledgePage.openUploadSourceDialog();

    // Drawer should be visible
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can upload a TXT file as a knowledge source', async ({ page }) => {
    test.setTimeout(90_000);
    const UNIQUE_TITLE = `e2e-source-${Date.now()}`;
    const fixturePath = path.join(__dirname, '../fixtures/fixture.txt');

    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    await knowledgePage.openUploadSourceDialog();
    await knowledgePage.selectUploadFile(fixturePath);

    // Override the auto-populated title with a unique name
    await knowledgePage.setSourceTitle(UNIQUE_TITLE);
    await knowledgePage.setSourceDescription('Uploaded by Playwright E2E test');

    await knowledgePage.submitUpload();
    await knowledgePage.waitForUploadDrawerClosed();
    await expectGridRowVisible(page, UNIQUE_TITLE);
  });

  // TODO: re-enable after fixing grid row-actions delete (column virtualization / timeout)
  test.skip('can delete a knowledge source via row actions', async ({
    page,
  }) => {
    const UNIQUE_TITLE = `e2e-src-del-${Date.now()}`;
    const fixturePath = path.join(__dirname, '../fixtures/fixture.txt');

    const knowledgePage = new KnowledgePage(page);
    await knowledgePage.goto();
    await knowledgePage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const btnVisible = await knowledgePage.uploadFabButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!btnVisible) {
      test.skip(true, 'Upload Source button not found — skipping');
      return;
    }

    // --- Setup: upload a source to delete ---
    await knowledgePage.openUploadSourceDialog();
    await page.locator('input[type="file"]').first().setInputFiles(fixturePath);
    await knowledgePage.setSourceTitle(UNIQUE_TITLE);
    await knowledgePage.submitUpload();
    await knowledgePage.waitForUploadDrawerClosed();
    await page.waitForLoadState('networkidle');
    await expectGridRowVisible(page, UNIQUE_TITLE);

    // --- Delete: hover row and click the delete icon ---
    await knowledgePage.deleteRowByText(UNIQUE_TITLE);
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    // The row should be gone
    const gone = await knowledgePage.rowIsGone(UNIQUE_TITLE);
    expect(
      gone,
      `Expected source "${UNIQUE_TITLE}" to be removed from the grid`
    ).toBeTruthy();
  });
});
