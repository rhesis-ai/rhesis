import { test, expect } from '@playwright/test';
import { TokensPage } from '../pages/TokensPage';
import { confirmDeleteDialog } from '../helpers/CrudHelper';

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
    await page.getByRole('textbox', { name: /token name/i }).fill(UNIQUE_NAME);
    await page.getByRole('button', { name: /^create$/i }).click();

    await expect(
      page.getByRole('heading', { name: /your new api token/i })
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible();

    await page.getByRole('button', { name: /^close$/i }).click();
    await expect(
      page.getByRole('heading', { name: /your new api token/i })
    ).not.toBeVisible({ timeout: 5_000 });

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
    await page
      .getByRole('textbox', { name: /token name/i })
      .fill(TOKEN_TO_DELETE);
    await page.getByRole('button', { name: /^create$/i }).click();

    await expect(
      page.getByRole('heading', { name: /your new api token/i })
    ).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: /^close$/i }).click();
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
