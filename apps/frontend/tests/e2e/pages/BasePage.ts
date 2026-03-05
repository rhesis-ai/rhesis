import { type Page, expect } from '@playwright/test';

/**
 * Abstract base class for all Page Object Models.
 * Provides shared helpers for common assertions used across all pages.
 */
export abstract class BasePage {
  constructor(protected readonly page: Page) {}

  /** Assert no server-level crash text is present in the page body. */
  async expectNoErrors() {
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(this.page.locator('body')).not.toContainText(
      'Application error'
    );
  }

  /** Wait until the main content area is visible (replaces raw networkidle waits). */
  async waitForContent(timeout = 15_000) {
    await this.page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout });
  }

  /** Assert a page heading with the given text/pattern is visible. */
  async expectHeading(name: string | RegExp) {
    await expect(this.page.getByRole('heading', { name }).first()).toBeVisible({
      timeout: 10_000,
    });
  }

  /**
   * Assert that either a data grid or an expected empty-state message is visible.
   * Settles the network first so the component has time to render.
   */
  async expectGridOrEmptyState(emptyStateText: string | RegExp) {
    await this.page.waitForLoadState('networkidle');
    const grid = this.page.locator('[role="grid"]');
    const empty = this.page.getByText(emptyStateText);
    const hasGrid = await grid.isVisible().catch(() => false);
    const hasEmpty = await empty.isVisible().catch(() => false);
    expect(
      hasGrid || hasEmpty,
      `Expected data grid or "${String(emptyStateText)}" to be visible`
    ).toBeTruthy();
  }
}
