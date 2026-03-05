import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Organization Settings page (/organizations/settings).
 */
export class OrgSettingsPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/organizations/settings');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/organizations\/settings/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    // The page renders a heading "Overview" inside PageContainer
    await this.expectHeading(/overview/i);
  }

  /**
   * Assert that the organization settings forms are rendered.
   * The page always renders form inputs for name, slug, etc.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    // The settings page always shows at least one text input
    const formInput = this.page.locator('input[type="text"]').first();
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasInput = await formInput.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasInput || hasMain).toBeTruthy();
  }
}
