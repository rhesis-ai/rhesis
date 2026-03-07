import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object for the Endpoints list page (/endpoints).
 */
export class EndpointsPage {
  readonly dataGrid: Locator;
  readonly newEndpointButton: Locator;

  constructor(private readonly page: Page) {
    this.dataGrid = page.locator('[role="grid"]');
    this.newEndpointButton = page
      .getByRole('button', { name: /new endpoint|add endpoint/i })
      .first();
  }

  async goto() {
    await this.page.goto('/endpoints');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/endpoints/);
    await expect(this.page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(this.page.locator('body')).not.toContainText(
      'Application error'
    );
  }

  async waitForContent() {
    // Wait for the main content area to be rendered — it is always present
    // whether the grid has data or shows an empty state, and is a more reliable
    // signal than networkidle on pages with background polling requests.
    await this.page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout: 15_000 });
  }

  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Navigate to new endpoint creation page. */
  async gotoNewEndpoint() {
    await this.page.goto('/endpoints/new');
  }

  /** Navigate to endpoint detail by identifier. */
  async gotoEndpointDetail(identifier: string) {
    await this.page.goto(`/endpoints/${identifier}`);
  }
}
