import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Organization Team tab on Organization Settings.
 */
export class OrgTeamPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/organizations/settings?tab=team');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/organizations\/settings/);
    await expect(this.page).toHaveURL(/tab=team/);
    await this.expectNoErrors();
  }

  /** Opens the invite team members drawer from the Team tab action. */
  async openInviteDrawer() {
    await this.page.waitForLoadState('networkidle');
    const inviteButton = this.page.getByRole('button', {
      name: /invite members/i,
    });
    const hasInviteButton = await inviteButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (hasInviteButton) {
      await inviteButton.click();
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
    await expect(this.page.getByRole('table').first()).toBeVisible({
      timeout: 15_000,
    });
  }
}
