import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Projects page (/projects).
 */
export class ProjectsPage {
  readonly heading: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole('heading', { name: /projects/i });
  }

  async goto() {
    await this.page.goto('/projects');
  }

  /** Assert the projects page loaded successfully. */
  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/projects/);
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  }
}
