import { test, expect } from '@playwright/test';
import { TokensPage } from '../pages/TokensPage';

/**
 * CRUD interaction tests for API Tokens.
 *
 * These tests exercise the full create → verify → delete flow against the
 * real backend running in Quick Start mode.
 */
test.describe('API Tokens — CRUD @crud', () => {
  const UNIQUE_NAME = `e2e-token-${Date.now()}`;

  test('can create an API token and see it in the list', async ({ page }) => {
    const tokensPage = new TokensPage(page);
    await tokensPage.goto();
    await tokensPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Open the create modal
    await tokensPage.openCreateTokenModal();

    // Fill in the token name
    await page.getByLabel('Token Name').fill(UNIQUE_NAME);

    // Submit — the default expiry (30 days) is pre-selected, so no change needed
    await page
      .getByRole('dialog')
      .getByRole('button', { name: /^create$/i })
      .click();

    // After creation the "Your New API Token" dialog appears
    await expect(
      page.getByRole('dialog', { name: /your new api token/i })
    ).toBeVisible({ timeout: 10_000 });

    // The token name is shown inside the dialog
    await expect(page.getByRole('dialog')).toContainText(UNIQUE_NAME);

    // Dismiss the token display dialog
    await page
      .getByRole('dialog')
      .getByRole('button', { name: /close/i })
      .click();

    // The create modal should now be gone
    await expect(
      page.getByRole('dialog', { name: /create new token|your new api token/i })
    ).not.toBeVisible({ timeout: 5_000 });

    // The new token should appear in the grid or list
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 10_000 });
  });

  test('can delete an API token', async ({ page }) => {
    const tokensPage = new TokensPage(page);
    const TOKEN_TO_DELETE = `e2e-del-token-${Date.now()}`;

    // --- Setup: create a token to delete ---
    await tokensPage.goto();
    await tokensPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tokensPage.openCreateTokenModal();
    await page.getByLabel('Token Name').fill(TOKEN_TO_DELETE);
    await page
      .getByRole('dialog')
      .getByRole('button', { name: /^create$/i })
      .click();

    // Dismiss the "Your New API Token" dialog
    await expect(
      page.getByRole('dialog', { name: /your new api token/i })
    ).toBeVisible({ timeout: 10_000 });
    await page
      .getByRole('dialog')
      .getByRole('button', { name: /close/i })
      .click();
    await page.waitForLoadState('networkidle');

    // Verify the token was created
    await expect(page.getByText(TOKEN_TO_DELETE)).toBeVisible({
      timeout: 10_000,
    });

    // --- Delete the token ---
    // Find the row and click the delete icon (last icon button in that row)
    const tokenRow = page.locator('[role="row"]', { hasText: TOKEN_TO_DELETE });
    await tokenRow.getByRole('button').last().click();

    // Confirm in the DeleteModal
    const deleteModal = page.getByRole('dialog');
    await expect(deleteModal).toBeVisible({ timeout: 5_000 });
    await deleteModal.getByRole('button', { name: /delete/i }).click();

    // The token should no longer appear in the list
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(TOKEN_TO_DELETE)).not.toBeVisible({
      timeout: 10_000,
    });
  });
});
