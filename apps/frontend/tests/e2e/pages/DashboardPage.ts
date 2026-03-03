import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Dashboard page (/dashboard).
 */
export class DashboardPage {
  readonly heading: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole('heading', { name: /dashboard/i });
  }

  async goto() {
    await this.page.goto('/dashboard');
  }

  /** Assert the dashboard page loaded successfully. */
  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/dashboard/);
    // The page should have rendered without a server error
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  }

  /**
   * Click a navigation item in the sidebar by its visible text.
   * Works for top-level sidebar items rendered by Toolpad's DashboardLayout.
   */
  async navigateTo(itemText: string) {
    // Toolpad renders nav items as list item buttons inside the drawer
    const navItem = this.page
      .locator('nav')
      .getByRole('link', { name: itemText });
    await navItem.click();
  }
}
