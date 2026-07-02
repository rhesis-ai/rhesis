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

    await expect(
      this.page.getByRole('heading', { name: /insights/i })
    ).toBeVisible({
      timeout: 10_000,
    });

    const noEndpoints = this.page.getByText(/no endpoints in this project/i);
    const noTestResults = this.page.getByText(/no test results yet/i);
    const searchBehaviors = this.page.getByPlaceholder(/search behaviors/i);
    const timeRange1M = this.page.getByRole('button', { name: '1M' });

    await expect(noEndpoints.or(noTestResults).or(searchBehaviors)).toBeVisible(
      { timeout: 15_000 }
    );

    if (await noEndpoints.isVisible()) {
      await expect(
        this.page.getByRole('button', { name: /go to endpoints/i })
      ).toBeVisible();
      return;
    }

    if (await noTestResults.isVisible()) {
      await expect(timeRange1M).toBeVisible();
      return;
    }

    await expect(searchBehaviors).toBeVisible();
    await expect(timeRange1M).toBeVisible();
    await expect(
      this.page.getByText(/\d+\.\d+%\s*pass rate/i).first()
    ).toBeVisible({
      timeout: 10_000,
    });
  }

  /** Expand a collapsible sidebar section (e.g. CONNECT for Endpoints). */
  async expandSidebarSection(sectionTitle: string) {
    const header = this.page
      .locator('nav')
      .getByText(sectionTitle, { exact: true });
    await header.waitFor({ state: 'visible', timeout: 10_000 });
    await header.click();
  }

  /** Projects moved to the organisation menu — not a primary sidebar link. */
  async navigateToProjectsViaOrgMenu() {
    await this.page
      .getByRole('button', { name: /open organisation menu/i })
      .click();
    await this.page.getByRole('menuitem', { name: 'Projects' }).click();
  }

  async navigateTo(itemText: string) {
    if (itemText === 'Projects') {
      await this.navigateToProjectsViaOrgMenu();
      return;
    }

    if (itemText === 'Endpoints') {
      await this.expandSidebarSection('CONNECT');
    }

    const navItem = this.page
      .locator('nav')
      .getByRole('link', { name: itemText });
    await navItem.waitFor({ state: 'visible', timeout: 10_000 });
    await navItem.scrollIntoViewIfNeeded();
    await navItem.click();
  }
}
