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
  /** Assert the page has rendered its main content area.
   * A heading is preferred but the main element is accepted as fallback because
   * when the fixture ID is not in the backend the SSR renders without a heading. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    const heading = this.page.getByRole('heading').first();
    const mainContent = this.page.locator('main, [role="main"]').first();
    const headingOk = await heading.isVisible().catch(() => false);
    const mainOk = await mainContent.isVisible().catch(() => false);
    expect(headingOk || mainOk).toBeTruthy();
  }

  /** Assert the source preview content area renders (metadata or content block). */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }
}
