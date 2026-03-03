import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Tests list page (/tests).
 */
export class TestsPage {
  readonly addButton: Locator;
  readonly dataGrid: Locator;

  constructor(private readonly page: Page) {
    this.addButton = page
      .getByRole('button', { name: /add test|new test/i })
      .first();
    this.dataGrid = page.locator('[role="grid"]');
  }

  async goto() {
    await this.page.goto('/tests');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/tests/);
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

  /** Returns true when the data grid is visible (data loaded). */
  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Click the Add / New Test button to open the creation flow. */
  async clickAddTest() {
    await this.addButton.click();
  }

  /** Get the number of visible rows (excluding header) in the data grid. */
  async getRowCount(): Promise<number> {
    const rows = this.page.locator('[role="row"]:not([aria-rowindex="1"])');
    return rows.count();
  }

  /** Open search/filter input if present. */
  async searchFor(text: string) {
    const searchInput = this.page.getByPlaceholder(/search|filter/i).first();
    await searchInput.fill(text);
    // Wait for the main content to remain visible (the grid may be empty after
    // filtering) rather than relying on networkidle.
    await this.page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout: 15_000 });
  }
}
