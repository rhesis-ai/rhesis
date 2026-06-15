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

  /** Assert the source preview heading renders (SSR + layout gate passed). */
  async expectHeadingVisible() {
    await this.waitForContent();
    await expect(
      this.page
        .getByRole('heading')
        .filter({ hasNotText: 'No project access' })
        .first()
    ).toBeVisible({ timeout: 10_000 });
  }

  /** Assert the source preview content area renders (metadata or content block). */
  async expectContentVisible() {
    await this.waitForContent();
    await expect(this.page.getByText('Source Information')).toBeVisible({
      timeout: 10_000,
    });
  }
}
