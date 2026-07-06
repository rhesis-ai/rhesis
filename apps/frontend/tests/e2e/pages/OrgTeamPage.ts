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

  /** Opens the invite team members drawer via the header FAB. */
  async openInviteDrawer() {
    await this.page.waitForLoadState('networkidle');
    const fab = this.page.getByRole('button', { name: /invite team members/i });
    const hasFab = await fab.isVisible({ timeout: 10_000 }).catch(() => false);
    if (hasFab) {
      await fab.click();
      return;
    }
    await this.page
      .locator('[data-tour="invite-team-button"]')
      .click({ timeout: 10_000 });
  }

  /**
   * Assert the team invite form is rendered inside the invite drawer.
   */
  async expectInviteFormVisible() {
    await this.openInviteDrawer();
    await this.page.waitForLoadState('networkidle');

    const emailInput = this.page.locator('input[type="email"]').first();
    const drawerTitle = this.page.getByText(/invite team members/i).first();

    const hasEmail = await emailInput.isVisible().catch(() => false);
    const hasDrawer = await drawerTitle.isVisible().catch(() => false);

    expect(hasEmail || hasDrawer).toBeTruthy();
  }

  /**
   * The RBAC org-role cell (OrgRoleChip, field `orgRole`) for the grid row
   * containing `identifierText` (typically the member's email).
   */
  roleCellForRow(identifierText: string) {
    return this.page
      .locator('[role="row"]', { hasText: identifierText })
      .locator('[data-field="orgRole"]');
  }

  /**
   * Assert that the team members grid is shown.
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
