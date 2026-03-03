import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the API Tokens page (/tokens).
 */
export class TokensPage {
  readonly dataGrid: Locator;
  readonly createTokenButton: Locator;

  constructor(private readonly page: Page) {
    this.dataGrid = page.locator('[role="grid"]');
    // The create button appears in both the toolbar (when tokens exist) and the empty state
    this.createTokenButton = page
      .getByRole('button', { name: /create api token/i })
      .first();
  }

  async goto() {
    await this.page.goto('/tokens');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/tokens/);
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(this.page.locator('body')).not.toContainText(
      'Application error'
    );
  }

  async waitForContent() {
    await this.page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout: 15_000 });
  }

  /** Click the "Create API Token" button (works regardless of empty/populated state). */
  async openCreateTokenModal() {
    await this.createTokenButton.click();
    await expect(
      this.page.getByRole('dialog', { name: /create new token/i })
    ).toBeVisible({ timeout: 5_000 });
  }

  /** Click the delete icon in the row that contains the given token name. */
  async deleteTokenByName(name: string) {
    const row = this.page.locator('[role="row"]', { hasText: name });
    // The delete icon button has tooltip "Delete Token"
    await row.getByRole('button').last().click();
  }
}
