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
    await this.page.waitForLoadState('networkidle');
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
    await this.page.waitForLoadState('networkidle');
  }
}
