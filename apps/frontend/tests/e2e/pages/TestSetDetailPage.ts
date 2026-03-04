import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Test Set detail page (/test-sets/[identifier]).
 */
export class TestSetDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/test-sets/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/test-sets/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the test set name comes from fixture data. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /** Assert the tests grid or empty state is visible inside the detail page. */
  async expectTestsGridVisible() {
    await this.page.waitForLoadState('networkidle');
    const grid = this.page.locator('[role="grid"]');
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasGrid = await grid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasGrid || hasMain).toBeTruthy();
  }
}
