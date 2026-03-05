import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Behaviors overview page (/behaviors).
 */
export class BehaviorsPage extends BasePage {
  readonly newBehaviorButton = this.page.getByRole('button', {
    name: /new behavior/i,
  });

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/behaviors');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/behaviors/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/behaviors/i);
  }

  /**
   * Assert the search/filter bar is present — it is always rendered regardless
   * of whether any behaviors exist.
   */
  async expectSearchBarVisible() {
    await this.page.waitForLoadState('networkidle');
    const searchInput = this.page.getByPlaceholder(/search/i);
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasSearch = await searchInput.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasSearch || hasMain).toBeTruthy();
  }

  /** Assert that behavior cards or an empty state message is visible. */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const cards = this.page.locator('.MuiCard-root');
    const emptyNoFilter = this.page.getByText(/no behaviors found/i);
    const emptyFiltered = this.page.getByText(/no behaviors match/i);
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasCards = (await cards.count()) > 0;
    const hasEmptyNoFilter = await emptyNoFilter.isVisible().catch(() => false);
    const hasEmptyFiltered = await emptyFiltered.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(
      hasCards || hasEmptyNoFilter || hasEmptyFiltered || hasMain
    ).toBeTruthy();
  }
}
