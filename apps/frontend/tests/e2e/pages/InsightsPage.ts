import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Insights page (/insights).
 */
export class InsightsPage extends BasePage {
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

  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible({ timeout: 10_000 });

    const bodyText = await this.page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(20);
  }

  async navigateTo(itemText: string) {
    const navItem = this.page
      .locator('nav')
      .getByRole('link', { name: itemText });
    await navItem.waitFor({ state: 'visible', timeout: 10_000 });
    await navItem.scrollIntoViewIfNeeded();
    await navItem.click();
  }
}
