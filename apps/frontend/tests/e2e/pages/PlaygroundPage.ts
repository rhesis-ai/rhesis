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
   * Assert that the playground page rendered — endpoint FAB, empty state, or chat area.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    const endpointFab = this.page.locator('main button').first();
    const noEndpointsMsg = this.page.getByText(/no endpoints available/i);
    const emptyState = this.page.getByText(
      /select an endpoint to start chatting/i
    );
    const chatArea = this.page.locator('main, [role="main"]').first();

    const hasEndpointFab = await endpointFab.isVisible().catch(() => false);
    const hasNoEndpoints = await noEndpointsMsg.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasMain = await chatArea.isVisible().catch(() => false);

    expect(
      hasEndpointFab || hasNoEndpoints || hasEmptyState || hasMain
    ).toBeTruthy();
  }
}
