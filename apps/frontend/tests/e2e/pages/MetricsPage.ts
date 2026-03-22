import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Metrics page (/metrics).
 * Only accessible to superusers.
 */
export class MetricsPage extends BasePage {
  readonly dataGrid = this.page.locator('[role="grid"]');

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/metrics');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/metrics/);
    await this.expectNoErrors();
  }

  /**
   * Returns true when the page renders metric cards or any main content.
   * The page may redirect to /dashboard for non-superusers.
   */
  async expectContentOrRedirect(): Promise<boolean> {
    await this.page.waitForLoadState('networkidle');
    const url = this.page.url();
    if (!url.includes('/metrics')) return false;
    const main = this.page.locator('main, [role="main"]').first();
    return main.isVisible().catch(() => false);
  }

  /** Type into the search input to filter metric cards. */
  async searchFor(text: string) {
    const searchInput = this.page.getByPlaceholder(/search/i).first();
    const visible = await searchInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!visible) return;
    await searchInput.fill(text);
    await this.page.waitForLoadState('networkidle');
  }

  /** Click a backend filter button (e.g. "Custom", "DeepEval", "Ragas"). */
  async clickBackendFilter(name: string | RegExp) {
    const btn = this.page.getByRole('button', { name }).first();
    const visible = await btn.isVisible({ timeout: 5_000 }).catch(() => false);
    if (visible) await btn.click();
  }

  /** Returns the count of visible MuiCard elements on the page. */
  async getCardCount(): Promise<number> {
    await this.page.waitForLoadState('networkidle');
    return this.page.locator('.MuiCard-root').count();
  }
}
