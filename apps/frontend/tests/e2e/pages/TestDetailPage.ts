import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Test detail page (/tests/[identifier]).
 */
export class TestDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/tests/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/tests/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the test prompt (truncated) comes from fixture data. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /** Assert the test detail content area renders (data table, charts, or tags). */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }
}
