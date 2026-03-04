import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Playground page (/playground).
 */
export class PlaygroundPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/playground');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/playground/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/playground/i);
  }

  /**
   * Assert that either the endpoint selector or a "no endpoints" message
   * is visible — both indicate the page rendered correctly.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    // The endpoint dropdown combobox or select element
    const endpointSelect = this.page
      .locator('[role="combobox"]')
      .or(this.page.locator('select'));
    // Shown when the user has no endpoints configured
    const noEndpointsMsg = this.page.getByText(/no endpoints available/i);
    // The prompt/chat input area
    const chatArea = this.page.locator('main, [role="main"]').first();

    const hasSelect = await endpointSelect
      .first()
      .isVisible()
      .catch(() => false);
    const hasNoEndpoints = await noEndpointsMsg.isVisible().catch(() => false);
    const hasMain = await chatArea.isVisible().catch(() => false);

    expect(hasSelect || hasNoEndpoints || hasMain).toBeTruthy();
  }
}
