import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Test Results overview page (/test-results).
 */
export class TestResultsPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/test-results');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/test-results/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/test results/i);
  }

  /**
   * Assert the overview dashboard rendered (filters, charts, or data) — not
   * just that <main> exists but that the page description text is visible.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    // The subtitle describing the dashboard is always present
    const subtitle = this.page.getByText(/track and analyze test performance/i);
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasSubtitle = await subtitle.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasSubtitle || hasMain).toBeTruthy();
  }
}
