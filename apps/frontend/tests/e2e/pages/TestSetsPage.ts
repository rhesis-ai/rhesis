import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Test Sets list page (/test-sets).
 */
export class TestSetsPage {
  readonly dataGrid: Locator;
  readonly newTestSetButton: Locator;

  constructor(private readonly page: Page) {
    this.dataGrid = page.locator('[role="grid"]');
    this.newTestSetButton = page
      .getByRole('button', { name: /new test set/i })
      .first();
  }

  async goto() {
    await this.page.goto('/test-sets');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/test-sets/);
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

  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Open the "New Test Set" drawer. */
  async openNewTestSetDrawer() {
    await this.newTestSetButton.click();
    // Wait for the drawer to slide in
    await this.page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /** Select a grid row that contains the given text. */
  async selectRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text });
    await row.locator('input[type="checkbox"]').click();
  }

  /** Click the "Delete Test Sets" toolbar button (only visible when rows are selected). */
  async clickDeleteSelected() {
    await this.page.getByRole('button', { name: /delete test sets/i }).click();
  }
}
