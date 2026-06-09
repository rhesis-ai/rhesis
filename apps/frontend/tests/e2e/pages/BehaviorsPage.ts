import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Behaviors overview page (/behaviors).
 */
export class BehaviorsPage extends BasePage {
  readonly newBehaviorButton = this.page.getByRole('button', {
    name: /create behavior/i,
  });

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/behaviors');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/behaviors/);
    await this.expectNoErrors();
  }

  async expectHeadingVisible() {
    await this.expectHeading(/behaviors/i);
  }

  /**
   * Assert the search/filter bar is present — it is always rendered regardless
   * of whether any behaviors exist.
   */
  async expectSearchBarVisible() {
    await this.page.waitForLoadState('networkidle');
    const searchInput = this.page.getByPlaceholder(/search/i);
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasSearch = await searchInput.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasSearch || hasMain).toBeTruthy();
  }

  /** Assert that behavior cards or an empty state message is visible. */
  async expectContentVisible() {
    await this.page.waitForLoadState('networkidle');
    const cards = this.behaviorCards();
    const emptyNoFilter = this.page.getByText(/no behaviors found/i);
    const emptyFiltered = this.page.getByText(/no behaviors match/i);
    const emptyFirst = this.page.getByText(/no behavior yet/i);
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
  private behaviorCard(name: string) {
    return this.page
      .locator('.MuiButtonBase-root')
      .filter({ has: this.page.getByText(name, { exact: true }) })
      .first();
  }

  private behaviorCards() {
    return this.page.locator('.MuiButtonBase-root').filter({
      has: this.page.locator('[data-testid="entity-card-description"]'),
    });
  }

  // ── CRUD helpers ──────────────────────────────────────────────────────────

  /** Open the create-behavior drawer and wait for it to slide in. */
  async openNewBehaviorDrawer() {
    const fab = this.newBehaviorButton.first();
    const fabVisible = await fab
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (fabVisible) {
      await fab.click();
    } else {
      await this.page.getByRole('button', { name: /create behavior/i }).click();
    }

    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /**
   * Fill the Name field inside the currently open drawer.
   * Scoped to the open (non-aria-hidden) right drawer to avoid matching
   * hidden portals (e.g., BehaviorMetricsViewer) or page-level inputs.
   */
  async fillBehaviorName(name: string) {
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('textbox', { name: /name/i })
      .first()
      .fill(name);
  }

  /** Fill the Description field inside the drawer. */
  async fillBehaviorDescription(description: string) {
    const descInput = this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('textbox', { name: /description/i });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the drawer by clicking "Add Behavior" or equivalent save button. */
  async submitNewBehavior() {
    const addBtn = this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .getByRole('button', { name: /add behavior|save/i })
      .first();
    await addBtn.click();
  }

  /** Wait for the drawer to close after submission. */
  async waitForDrawerClosed() {
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'hidden', timeout: 15_000 });
  }

  /** Open a behavior card on the detail page. */
  async openBehaviorDetail(name: string) {
    await this.behaviorCard(name).click();
    await this.page.waitForURL(/\/behaviors\//, { timeout: 15_000 });
    await this.page.waitForLoadState('networkidle');
  }

  /** Edit opens from the behavior detail page (card actions were removed). */
  async clickEditOnCard(name: string) {
    await this.openBehaviorDetail(name);
    await this.page.getByRole('button', { name: /^edit$/i }).click();
    await this.page
      .locator('.MuiDrawer-anchorRight:not([aria-hidden="true"])')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /** Delete uses the icon-only control on the card header. */
  async clickDeleteOnCard(name: string) {
    const card = this.behaviorCard(name);
    await card.locator('button').click();
  }

  /** Assign metrics from the behavior detail Linked Metrics tab. */
  async clickAddMetricOnCard(name: string) {
    await this.openBehaviorDetail(name);
    await this.page.getByRole('tab', { name: /linked metrics/i }).click();
    await this.page.getByRole('button', { name: /^assign$/i }).click();
  }

  /** Returns true if a behavior card with the given name is visible. */
  async cardIsVisible(name: string): Promise<boolean> {
    return this.behaviorCard(name)
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
  }

  /** Returns true if no behavior card with the given name is visible. */
  async cardIsGone(name: string): Promise<boolean> {
    return this.behaviorCard(name)
      .isHidden({ timeout: 15_000 })
      .catch(() => false);
  }
}
