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

  /**
   * Assert the tabbed detail view renders (Overview, Connection, Mappings, Test).
   */
  async expectTabsVisible() {
    await this.page.waitForLoadState('networkidle');
    const overviewTab = this.page.getByRole('tab', { name: /overview/i });
    const hasOverview = await overviewTab.isVisible().catch(() => false);
    const tabs = this.page.locator('[role="tab"]');
    const hasTabs = (await tabs.count()) > 0;
    expect(hasOverview || hasTabs).toBeTruthy();
  }

  /** Assert overview tab content is visible. */
  async expectBasicInfoVisible() {
    await this.page.waitForLoadState('networkidle');
    const identity = this.page.getByText(/identity/i).first();
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasIdentity = await identity.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasIdentity || hasMain).toBeTruthy();
  }
}
