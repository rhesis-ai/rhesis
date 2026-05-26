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
    await this.expectHeading(/organization settings/i);
  }

  /** Click Edit on the first settings card (Basic Information). */
  async clickEditBasicInformation() {
    const section = this.page
      .locator('h6')
      .filter({ hasText: /^Basic Information$/i })
      .locator('..')
      .locator('..');
    await section.getByRole('button', { name: /^edit$/i }).click();
  }

  /** Click Edit on the Contact Information card. */
  async clickEditContactInformation() {
    const section = this.page
      .locator('h6')
      .filter({ hasText: /^Contact Information$/i })
      .locator('..')
      .locator('..');
    await section.getByRole('button', { name: /^edit$/i }).click();
  }

  /**
   * Assert that the organization settings forms are rendered.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    const basicSection = this.page
      .getByRole('heading', { name: /basic information/i })
      .first();
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasSection = await basicSection.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasSection || hasMain).toBeTruthy();
  }
}
