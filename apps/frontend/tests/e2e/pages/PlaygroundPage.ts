import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Playground page (/playground).
 */
export class PlaygroundPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/playground');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/playground/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/playground/i);
  }

  /** Wait for endpoint options to finish loading. */
  async waitForEndpointsReady() {
    await this.page.waitForLoadState('networkidle');

    const endpointFab = this.page.getByRole('button', {
      name: /select endpoint/i,
    });
    if (
      !(await endpointFab.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      return;
    }

    await endpointFab.click();
    const drawer = this.openDrawer();
    await expect(drawer.getByText('Select Endpoint').first()).toBeVisible({
      timeout: 10_000,
    });

    const loading = drawer.getByText(/loading endpoints/i);
    if (await loading.isVisible().catch(() => false)) {
      await loading.waitFor({ state: 'hidden', timeout: 20_000 });
    }

    await this.page.keyboard.press('Escape');
  }

  /** Opens the endpoint selection drawer via the header FAB. */
  async openEndpointDrawer() {
    await this.page.getByRole('button', { name: /select endpoint/i }).click();
    const drawer = this.openDrawer();
    await expect(drawer.getByText('Select Endpoint').first()).toBeVisible({
      timeout: 10_000,
    });
  }

  /**
   * Returns a locator scoped to the currently-open MUI drawer.
   */
  openDrawer() {
    return this.page.locator('[role="presentation"]').filter({ visible: true });
  }

  /**
   * Select the first available endpoint in the drawer and confirm.
   * Returns false when the selector or options are unavailable.
   */
  async selectFirstEndpointInDrawer(): Promise<boolean> {
    const endpointFab = this.page.getByRole('button', {
      name: /select endpoint/i,
    });
    const hasFab = await endpointFab
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasFab) return false;

    await this.openEndpointDrawer();

    const drawer = this.openDrawer();
    const loading = drawer.getByText(/loading endpoints/i);
    if (await loading.isVisible().catch(() => false)) {
      await loading.waitFor({ state: 'hidden', timeout: 20_000 });
    }

    const noEndpointsAlert = drawer.getByText(/no endpoints available/i);
    if (
      await noEndpointsAlert.isVisible({ timeout: 3_000 }).catch(() => false)
    ) {
      await this.page.keyboard.press('Escape');
      return false;
    }

    const combobox = drawer.getByRole('combobox', { name: /select endpoint/i });
    const hasCombobox = await combobox
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasCombobox) {
      await this.page.keyboard.press('Escape');
      return false;
    }

    await combobox.click();
    const firstOption = this.page
      .getByRole('option')
      .filter({ hasNot: this.page.getByText(/choose an endpoint/i) })
      .first();
    const hasOption = await firstOption
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasOption) {
      await this.page.keyboard.press('Escape');
      await this.page.keyboard.press('Escape');
      return false;
    }

    await firstOption.click();
    await drawer.getByRole('button', { name: /^select$/i }).click();
    await this.page.waitForLoadState('networkidle');
    return true;
  }

  /**
   * Assert that the playground page rendered — endpoint FAB, empty state, or chat area.
   */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');

    const endpointFab = this.page.getByRole('button', {
      name: /select endpoint/i,
    });
    const emptyState = this.page.getByText(
      /select an endpoint to start chatting/i
    );
    const chatArea = this.page.locator('main, [role="main"]').first();

    const hasFab = await endpointFab.isVisible().catch(() => false);
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasMain = await chatArea.isVisible().catch(() => false);

    expect(hasFab || hasEmptyState || hasMain).toBeTruthy();
  }
}
