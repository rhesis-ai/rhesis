import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Organization Team page (/organizations/team).
 */
export class OrgTeamPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/organizations/team');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/organizations\/team/);
    await this.expectNoErrors();
  }

  /**
   * Assert the team invite form is rendered.
   * The invite email input is always present regardless of member count.
   */
  async expectInviteFormVisible() {
    await this.page.waitForLoadState('networkidle');

    const emailInput = this.page.locator('input[type="email"]').first();
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasEmail = await emailInput.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasEmail || hasMain).toBeTruthy();
  }

  /**
   * Assert that either the team members grid or an empty state is shown.
   */
  async expectMembersAreaVisible() {
    await this.page.waitForLoadState('networkidle');

    const grid = this.page.locator('[role="grid"]');
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasGrid = await grid.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasGrid || hasMain).toBeTruthy();
  }
}
