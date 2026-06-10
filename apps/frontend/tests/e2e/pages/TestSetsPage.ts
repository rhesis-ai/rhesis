import { type Page, type Locator, expect } from '@playwright/test';
import {
  expectOpenDrawerTitle,
  deleteGridRowByText,
} from '../helpers/CrudHelper';

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
    const emptyAction = this.page
      .getByRole('button', { name: /create test set/i })
      .first();
    const emptyVisible = await emptyAction
      .isVisible({ timeout: 3_000 })
      .catch(() => false);
    if (emptyVisible) {
      await emptyAction.click();
    } else {
      await this.newTestSetButton.click();
    }

    await expectOpenDrawerTitle(this.page, /^new test set$/i);
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    await deleteGridRowByText(this.page, text);
  }
}
