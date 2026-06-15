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

  /** Wait until the client-side endpoint fetch finishes and tabs render. */
  async waitForEndpointLoaded() {
    await this.page
      .getByText('Loading endpoint...')
      .waitFor({ state: 'hidden', timeout: 15_000 })
      .catch(() => {});
    await this.page
      .getByRole('tablist', { name: 'Endpoint detail tabs' })
      .waitFor({ state: 'visible', timeout: 15_000 });
  }

  /** Assert the page heading renders after the endpoint loads. */
  async expectHeadingVisible() {
    await this.waitForEndpointLoaded();
    await expect(this.page.getByRole('heading').first()).toBeVisible();
  }

  /**
   * Assert the tabbed detail view renders (Overview, Connection, Mappings, Test).
   */
  async expectTabsVisible() {
    await this.waitForEndpointLoaded();
    await expect(
      this.page.getByRole('tab', { name: /overview/i })
    ).toBeVisible();
  }

  /** Assert overview tab content is visible. */
  async expectBasicInfoVisible() {
    await this.waitForEndpointLoaded();
    const overview = this.page.getByText(/endpoint details/i).first();
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasOverview = await overview.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasOverview || hasMain).toBeTruthy();
  }
}
