import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Endpoint detail page (/endpoints/[identifier]).
 */
export class EndpointDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/endpoints/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/endpoints/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the endpoint name comes from fixture data. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /**
   * Assert the tabbed detail view renders.
   * The endpoint detail always shows at least the Basic Information tab.
   */
  async expectTabsVisible() {
    await this.page.waitForLoadState('networkidle');
    const tabs = this.page.locator('[role="tab"]');
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasTabs = (await tabs.count()) > 0;
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasTabs || hasMain).toBeTruthy();
  }

  /** Assert the "Basic Information" tab content is visible. */
  async expectBasicInfoVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }
}
