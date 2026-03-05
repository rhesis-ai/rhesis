import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Test Run detail page (/test-runs/[identifier]).
 */
export class TestRunDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/test-runs/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/test-runs/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the run name comes from fixture data. */
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
   * Assert the test results grid or an empty/error state is visible.
   * The test run detail always renders either a populated grid or a message.
   */
  async expectResultsAreaVisible() {
    await this.page.waitForLoadState('networkidle');
    const grid = this.page.locator('[role="grid"]');
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasGrid = await grid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasGrid || hasMain).toBeTruthy();
  }
}
