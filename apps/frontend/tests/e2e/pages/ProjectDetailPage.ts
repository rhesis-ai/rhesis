import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Project detail page (/projects/[identifier]).
 */
export class ProjectDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/projects/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/projects/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the project name comes from fixture data. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /** Assert the project content area (metadata or endpoints section) is rendered. */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }
}
