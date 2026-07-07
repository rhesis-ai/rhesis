import { type Page, type Locator, expect } from '@playwright/test';
import {
  expectOpenDrawerTitle,
  deleteGridRowByText,
} from '../helpers/CrudHelper';

/**
 * Page Object for the API Tokens page (/tokens).
 */
export class TokensPage {
  readonly dataGrid: Locator;
  readonly createTokenButton: Locator;
  /** RBAC (EE) scope section in the create-token drawer — see TokenScopeField. */
  readonly scopeField: Locator;

  constructor(private readonly page: Page) {
    this.dataGrid = page.locator('[role="grid"]');
    this.createTokenButton = page
      .getByRole('button', { name: /create api token/i })
      .first();
    this.scopeField = page.getByText(/token permissions/i);
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

  /** Open the create-token drawer (BaseDrawer, not a dialog). */
  async openCreateTokenModal() {
    await this.createTokenButton.click();
    await expectOpenDrawerTitle(this.page, /create new token/i);
  }

  /** Delete a token via the hover-revealed row-actions delete icon. */
  async deleteRowByText(name: string) {
    await deleteGridRowByText(this.page, name);
  }
}
