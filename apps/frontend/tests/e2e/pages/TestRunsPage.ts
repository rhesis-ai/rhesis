import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Test Runs list page (/test-runs).
 */
export class TestRunsPage {
  readonly dataGrid: Locator;
  readonly pageTitle: Locator;

  constructor(private readonly page: Page) {
    this.dataGrid = page.locator('[role="grid"]');
    this.pageTitle = page.getByRole('heading', { name: /test runs/i }).first();
  }

  async goto() {
    await this.page.goto('/test-runs');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/test-runs/);
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(this.page.locator('body')).not.toContainText(
      'Application error'
    );
  }

  async waitForContent() {
    // Wait for the main content area to be rendered — it is always present
    // whether the grid has data or shows an empty state, and is a more reliable
    // signal than networkidle on pages with background polling requests.
    await this.page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout: 15_000 });
  }

  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Navigate to a test run detail page by clicking a row. */
  async clickFirstRow() {
    const firstDataRow = this.page.locator('[role="row"]').nth(1);
    await firstDataRow.click();
  }

  /** Wait for the detail page to navigate away from the list. */
  async expectDetailPageLoaded() {
    await expect(this.page).toHaveURL(/\/test-runs\/.+/);
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  }
}
