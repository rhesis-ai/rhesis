import { type Page, expect } from '@playwright/test';
import { dismissTermsGateIfVisible } from '../helpers/TermsHelper';
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

    const noEndpoints = this.page.getByRole('heading', {
      name: /no endpoints in this project/i,
    });
    const noTestResults = this.page.getByRole('heading', {
      name: /no test results yet/i,
    });
    const searchBehaviors = this.page.getByPlaceholder(/search behaviors/i);
    const passRateMetric = this.page.getByText(/\d+\.\d+%\s*pass rate/i);
    const timeRange1M = this.page.getByRole('button', { name: '1M' });

    // Wait for endpoint auto-selection and insights fetch to settle.
    await expect(
      noEndpoints.or(noTestResults).or(searchBehaviors)
    ).toBeVisible({
      timeout: 30_000,
    });

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

    await expect(this.page.getByPlaceholder(/search behaviors/i)).toBeVisible();
    await expect(timeRange1M).toBeVisible();
    await expect(passRateMetric.first()).toBeVisible({ timeout: 15_000 });
  }

  private mainNav() {
    return this.page.locator('nav[aria-label="Main navigation"]');
  }

  /** Expand the sidebar when it is in icon-only mode. */
  async ensureSidebarExpanded() {
    const expandButton = this.page.getByRole('button', {
      name: /expand sidebar/i,
    });
    if (await expandButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await expandButton.click();
    }
  }

  /** Wait until primary sidebar navigation is interactive. */
  async waitForNavReady() {
    await this.ensureSidebarExpanded();
    await this.mainNav().waitFor({ state: 'visible', timeout: 15_000 });
    await dismissTermsGateIfVisible(this.page);
  }

  /** Expand a collapsible sidebar section (e.g. CONNECT for Endpoints). */
  async expandSidebarSection(sectionTitle: string) {
    const header = this.mainNav().getByText(sectionTitle, { exact: true });
    await header.waitFor({ state: 'visible', timeout: 15_000 });
    await header.click();
  }

  /** Projects moved to the organisation menu — not a primary sidebar link. */
  async navigateToProjectsViaOrgMenu() {
    const orgMenuButton = this.page.getByRole('button', {
      name: /open organisation menu/i,
    });
    await orgMenuButton.waitFor({ state: 'visible', timeout: 15_000 });
    await orgMenuButton.click();

    const popover = this.page.locator('.MuiPopover-root').last();
    await popover.waitFor({ state: 'visible', timeout: 15_000 });
    await popover.getByText('Projects', { exact: true }).click();
  }

  async navigateTo(itemText: string) {
    await this.waitForNavReady();

    if (itemText === 'Projects') {
      await this.navigateToProjectsViaOrgMenu();
      return;
    }

    if (itemText === 'Endpoints') {
      await this.mainNav()
        .getByText('CONNECT', { exact: true })
        .waitFor({ state: 'visible', timeout: 15_000 });

      const endpointLink = this.mainNav().locator('a[href="/endpoints"]');
      if (!(await endpointLink.isVisible().catch(() => false))) {
        await this.expandSidebarSection('CONNECT');
      }

      await endpointLink.waitFor({ state: 'visible', timeout: 15_000 });
      await endpointLink.scrollIntoViewIfNeeded();
      await endpointLink.click();
      return;
    }

    const navItem = this.mainNav().getByRole('link', { name: itemText });
    await navItem.waitFor({ state: 'visible', timeout: 15_000 });
    await navItem.scrollIntoViewIfNeeded();
    await navItem.click();
  }
}
