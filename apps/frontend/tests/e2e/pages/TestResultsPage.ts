import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * @deprecated Test Results overview moved to /insights. /test-results redirects.
 */
export class TestResultsPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/insights');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/insights/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/insights/i);
  }

  /**
   * Assert the overview dashboard rendered (filters, charts, or data) — not
   * just that <main> exists but that the page description text is visible.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible({ timeout: 10_000 });
  }
}
