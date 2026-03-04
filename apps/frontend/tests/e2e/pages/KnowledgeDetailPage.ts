import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Knowledge (Source Preview) detail page (/knowledge/[identifier]).
 */
export class KnowledgeDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/knowledge/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/knowledge/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the source file name comes from fixture data. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /** Assert the source preview content area renders (metadata or content block). */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }
}
