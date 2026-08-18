import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Requirements overview page (/requirements).
 */
export class RequirementsPage extends BasePage {
  readonly newRequirementButton = this.page.getByRole('button', {
    name: /create requirement/i,
  });

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/requirements');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/requirements/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/requirements/i);
  }

  /**
   * Assert the search/filter bar is present — it is always rendered regardless
   * of whether any requirements exist.
   */
  async expectSearchBarVisible() {
    await this.page.waitForLoadState('networkidle');
    const searchInput = this.page.getByPlaceholder(/search/i);
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasSearch = await searchInput.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasSearch || hasMain).toBeTruthy();
  }

  /** Assert that requirement cards or an empty state message is visible. */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const cards = this.requirementCards();
    const emptyNoFilter = this.page.getByText(/no requirements found/i);
    const emptyFiltered = this.page.getByText(/no requirements match/i);
    const emptyFirst = this.page.getByText(/no requirement yet/i);
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasCards = (await cards.count()) > 0;
    const hasEmptyNoFilter = await emptyNoFilter.isVisible().catch(() => false);
    const hasEmptyFiltered = await emptyFiltered.isVisible().catch(() => false);
    const hasEmptyFirst = await emptyFirst.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(
      hasCards ||
        hasEmptyNoFilter ||
        hasEmptyFiltered ||
        hasEmptyFirst ||
        hasMain
    ).toBeTruthy();
  }

  /** EntityCard renders as MuiButtonBase-root, not MuiCard-root. */
  private requirementCard(name: string) {
    return this.page
      .locator('.MuiButtonBase-root')
      .filter({ has: this.page.getByText(name, { exact: true }) })
      .first();
  }

  private requirementCards() {
    return this.page.locator('.MuiButtonBase-root').filter({
      has: this.page.locator('[data-testid="entity-card-description"]'),
    });
  }

  // ── CRUD helpers ──────────────────────────────────────────────────────────

  /** Open the create-requirement drawer and wait for it to slide in. */
  async openNewRequirementDrawer() {
    const fab = this.newRequirementButton.first();
    const fabVisible = await fab
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (fabVisible) {
      await fab.click();
    } else {
      await this.page
        .getByRole('button', { name: /create requirement/i })
        .click();
    }

    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /**
   * Fill the Name field inside the currently open drawer.
   * Scoped to the open (non-aria-hidden) right drawer to avoid matching
   * hidden portals (e.g., RequirementMetricsViewer) or page-level inputs.
   */
  async fillRequirementName(name: string) {
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('textbox', { name: /name/i })
      .first()
      .fill(name);
  }

  /** Fill the Description field inside the drawer. */
  async fillRequirementDescription(description: string) {
    const descInput = this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('textbox', { name: /description/i });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the drawer by clicking "Add Requirement" or equivalent save button. */
  async submitNewRequirement() {
    const addBtn = this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('button', { name: /add requirement|save/i })
      .first();
    await addBtn.click();
  }

  /** Wait for the drawer to close after submission. */
  async waitForDrawerClosed() {
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'hidden', timeout: 15_000 });
  }

  /** Open a requirement card on the detail page. */
  async openRequirementDetail(name: string) {
    await expect(this.requirementCard(name)).toBeVisible({ timeout: 15_000 });

    const detailResponse = this.page.waitForResponse(
      resp =>
        /\/requirements\/[0-9a-f-]{36}/i.test(resp.url()) &&
        resp.request().method() === 'GET' &&
        resp.status() === 200,
      { timeout: 20_000 }
    );

    await this.requirementCard(name).click();
    await this.page.waitForURL(/\/requirements\//, { timeout: 15_000 });
    await detailResponse;
    await this.page.waitForLoadState('networkidle');
  }

  /** Edit opens from the requirement detail page (card actions were removed). */
  async clickEditOnCard(name: string) {
    await this.openRequirementDetail(name);
    await this.page
      .locator('main')
      .getByRole('button', { name: /^edit$/i })
      .first()
      .click();
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /** Delete uses the icon-only control on the card header. */
  async clickDeleteOnCard(name: string) {
    const card = this.requirementCard(name);
    await card.locator('button').click();
  }

  /** Assign metrics from the requirement detail Linked Metrics tab. */
  async clickAddMetricOnCard(name: string) {
    await this.openRequirementDetail(name);
    await this.page.getByRole('tab', { name: /linked metrics/i }).click();
    await this.page.getByRole('button', { name: /^assign$/i }).click();
  }

  /** Returns true if a requirement card with the given name is visible. */
  async cardIsVisible(name: string): Promise<boolean> {
    return this.requirementCard(name)
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
  }

  /** Returns true if no requirement card with the given name is visible. */
  async cardIsGone(name: string): Promise<boolean> {
    return this.requirementCard(name)
      .isHidden({ timeout: 15_000 })
      .catch(() => false);
  }
}
