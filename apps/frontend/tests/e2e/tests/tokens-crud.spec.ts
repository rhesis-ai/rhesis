import { test, expect } from '@playwright/test';
import { TokensPage } from '../pages/TokensPage';
import {
  confirmDeleteDialog,
  expectOpenDrawerTitle,
  openDrawer,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for API Tokens.
 *
 * These tests exercise the full create → verify → delete flow against the
 * real backend running in Quick Start mode.
 */
test.describe('API Tokens — CRUD @crud', () => {
  test('can create an API token and see it in the list', async ({ page }) => {
    const UNIQUE_NAME = `e2e-token-${Date.now()}`;
    const tokensPage = new TokensPage(page);
    await tokensPage.goto();
    await tokensPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tokensPage.openCreateTokenModal();
    const createDrawer = openDrawer(page);
    await createDrawer
      .getByRole('textbox', { name: /token name/i })
      .fill(UNIQUE_NAME);
    await createDrawer.getByRole('button', { name: /^create$/i }).click();
    await expectOpenDrawerTitle(page, /your new api token/i, 15_000);

    const tokenDrawer = openDrawer(page);
    await expect(tokenDrawer.getByText(UNIQUE_NAME)).toBeVisible();
    await tokenDrawer.getByRole('button', { name: /^close$/i }).click();
    await waitForDrawerClosed(page);

    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 10_000 });
  });

  test('can delete an API token', async ({ page }) => {
    const tokensPage = new TokensPage(page);
    const TOKEN_TO_DELETE = `e2e-del-token-${Date.now()}`;

    await tokensPage.goto();
    await tokensPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tokensPage.openCreateTokenModal();
    const createDrawer = openDrawer(page);
    await createDrawer
      .getByRole('textbox', { name: /token name/i })
      .fill(TOKEN_TO_DELETE);
    await createDrawer.getByRole('button', { name: /^create$/i }).click();
    await expectOpenDrawerTitle(page, /your new api token/i, 15_000);

    const tokenDrawer = openDrawer(page);
    await tokenDrawer.getByRole('button', { name: /^close$/i }).click();
    await waitForDrawerClosed(page);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(TOKEN_TO_DELETE)).toBeVisible({
      timeout: 10_000,
    });

    await tokensPage.deleteRowByText(TOKEN_TO_DELETE);
    await confirmDeleteDialog(page);

    await page.waitForLoadState('networkidle');
    await expect(page.getByText(TOKEN_TO_DELETE)).not.toBeVisible({
      timeout: 10_000,
    });
  });
});
