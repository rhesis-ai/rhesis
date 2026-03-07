import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Dashboard page (/dashboard).
 */
export class DashboardPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/dashboard');
  }

  /** Assert the dashboard page loaded successfully. */
  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/dashboard/);
    await this.expectNoErrors();
  }

  /**
   * Assert that the main content area has rendered content.
   * The dashboard shows a spinner while loading, then KPI widgets + charts.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();

    // Page body should have substantial content beyond just a spinner
    const bodyText = await this.page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(20);
  }

  /**
   * Click a navigation item in the sidebar by its visible text.
   * Works for top-level sidebar items rendered by Toolpad's DashboardLayout.
   */
  async navigateTo(itemText: string) {
    const navItem = this.page
      .locator('nav')
      .getByRole('link', { name: itemText });
    await navItem.click();
  }

  /**
   * Expand a parent nav item and click a child item.
   * Used for nested navigation sections such as the Organization submenu.
   */
  async navigateToNested(parentText: string, childText: string) {
    // The parent is a button (collapsible), not a link
    const parent = this.page
      .locator('nav')
      .getByRole('button', { name: new RegExp(parentText, 'i') });
    await parent.click();

    const child = this.page
      .locator('nav')
      .getByRole('link', { name: childText });
    await child.click();
  }
}
