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
    const fab = this.newTestSetButton;
    const fabVisible = await fab
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (fabVisible) {
      await fab.click();
    } else {
      await this.page.getByRole('button', { name: /create test set/i }).click();
    }

    await expect(
      this.page.getByRole('heading', { name: /^new test set$/i })
    ).toBeVisible({ timeout: 10_000 });
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text }).first();
    await row.scrollIntoViewIfNeeded();
    await row.hover();
    await row.locator('.row-actions button').last().click();
  }
}
