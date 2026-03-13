import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Traces page (/traces).
 */
export class TracesPage extends BasePage {
  readonly dataGrid = this.page.locator('[role="grid"]');

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/traces');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/traces/);
    await this.expectNoErrors();
  }

  /** Returns true when the data grid or empty state is visible. */
  async hasContent(): Promise<boolean> {
    await this.page.waitForLoadState('networkidle');
    const grid = this.page.locator('[role="grid"]');
    const main = this.page.locator('main, [role="main"]').first();
    const hasGrid = await grid.isVisible().catch(() => false);
    const hasMain = await main.isVisible().catch(() => false);
    return hasGrid || hasMain;
  }

  /** Returns true if at least one data row (non-header) is visible. */
  async hasTraceRows(): Promise<boolean> {
    await this.page.waitForLoadState('networkidle');
    const rows = this.page.locator('[role="row"]');
    const count = await rows.count().catch(() => 0);
    return count > 1;
  }

  /** Click the first data row to open the trace drawer. */
  async clickFirstTraceRow() {
    const firstDataRow = this.page.locator('[role="row"]').nth(1);
    await firstDataRow.click();
  }

  /**
   * Wait for the trace drawer to open.
   * The drawer is a MUI Drawer rendered as role="presentation".
   */
  async waitForDrawerOpen() {
    await this.page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /** Click a view-switcher tab inside the trace drawer (Tree / Sequence / Graph). */
  async clickDrawerViewTab(name: string | RegExp) {
    const tab = this.page
      .getByRole('presentation')
      .getByRole('tab', { name })
      .first();
    const visible = await tab.isVisible({ timeout: 5_000 }).catch(() => false);
    if (visible) await tab.click();
  }

  /** Returns true if the trace drawer is visible. */
  async isDrawerOpen(): Promise<boolean> {
    return this.page
      .getByRole('presentation')
      .isVisible()
      .catch(() => false);
  }
}
