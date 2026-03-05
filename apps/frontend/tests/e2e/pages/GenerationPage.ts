import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Generation page (/generation).
 *
 * This page is a redirect shim — it immediately redirects to
 * /tests?openGeneration=true rather than rendering its own UI.
 */
export class GenerationPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/generation');
  }

  /**
   * Assert that the redirect occurred and we landed on the Tests page
   * with the openGeneration query parameter.
   */
  async expectRedirectedToTests() {
    // Wait for the redirect to complete
    await this.page.waitForURL(/\/tests/, { timeout: 10_000 });
    await expect(this.page).toHaveURL(/\/tests/);
    await this.expectNoErrors();
  }
}
