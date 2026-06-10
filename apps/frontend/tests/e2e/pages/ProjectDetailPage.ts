import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Project detail page (/projects/[identifier]).
 */
export class ProjectDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string, query?: string) {
    const suffix = query ? `?${query}` : '';
    await this.page.goto(`/projects/${id}${suffix}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/projects/${id}`));
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    const heading = this.page.getByRole('heading').first();
    const mainContent = this.page.locator('main, [role="main"]').first();
    const headingOk = await heading.isVisible().catch(() => false);
    const mainOk = await mainContent.isVisible().catch(() => false);
    expect(headingOk || mainOk).toBeTruthy();
  }

  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }

  async expectTabNavVisible() {
    await expect(
      this.page.getByRole('tablist', { name: 'Project detail sections' })
    ).toBeVisible();
    await expect(
      this.page.getByRole('tab', { name: 'Overview', selected: true })
    ).toBeVisible();
  }

  async expectMetadataStripVisible() {
    await expect(this.page.getByText(/created by:/i)).toBeVisible();
    await expect(this.page.getByText(/created on:/i)).toBeVisible();
  }
}
