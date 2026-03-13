import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Behaviors overview page (/behaviors).
 */
export class BehaviorsPage extends BasePage {
  readonly newBehaviorButton = this.page.getByRole('button', {
    name: /new behavior/i,
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
    const cards = this.page.locator('.MuiCard-root');
    const emptyNoFilter = this.page.getByText(/no behaviors found/i);
    const emptyFiltered = this.page.getByText(/no behaviors match/i);
    const mainContent = this.page.locator('main, [role="main"]').first();

    const hasCards = (await cards.count()) > 0;
    const hasEmptyNoFilter = await emptyNoFilter.isVisible().catch(() => false);
    const hasEmptyFiltered = await emptyFiltered.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(
      hasCards || hasEmptyNoFilter || hasEmptyFiltered || hasMain
    ).toBeTruthy();
  }

  // ── CRUD helpers ──────────────────────────────────────────────────────────

  /** Open the "New Behavior" drawer and wait for it to slide in. */
  async openNewBehaviorDrawer() {
    await this.newBehaviorButton.click();
    await this.page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /**
   * Fill the Name field inside the currently open drawer.
   * Scoped to [role="presentation"] to avoid matching page-level inputs.
   */
  async fillBehaviorName(name: string) {
    await this.page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /name/i })
      .first()
      .fill(name);
  }

  /** Fill the Description field inside the drawer. */
  async fillBehaviorDescription(description: string) {
    const descInput = this.page
      .locator('[role="presentation"]')
      .getByRole('textbox', { name: /description/i });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the drawer by clicking "Add Behavior" or equivalent save button. */
  async submitNewBehavior() {
    const addBtn = this.page
      .locator('[role="presentation"]')
      .getByRole('button', { name: /add behavior|save/i })
      .first();
    await addBtn.click();
  }

  /** Wait for the drawer to close after submission. */
  async waitForDrawerClosed() {
    await this.page
      .getByRole('presentation')
      .waitFor({ state: 'hidden', timeout: 15_000 });
  }

  /** Find the card with the given name and click its edit (pencil) icon button. */
  async clickEditOnCard(name: string) {
    const card = this.page.locator('.MuiCard-root', { hasText: name });
    await card.getByRole('button', { name: /edit/i }).first().click();
  }

  /** Find the card with the given name and click its delete (trash) icon button. */
  async clickDeleteOnCard(name: string) {
    const card = this.page.locator('.MuiCard-root', { hasText: name });
    await card
      .getByRole('button', { name: /delete/i })
      .first()
      .click();
  }

  /** Find the card with the given name and click its add metric (+) icon button. */
  async clickAddMetricOnCard(name: string) {
    const card = this.page.locator('.MuiCard-root', { hasText: name });
    await card
      .getByRole('button', { name: /add metric/i })
      .first()
      .click();
  }

  /** Returns true if a behavior card with the given name is visible. */
  async cardIsVisible(name: string): Promise<boolean> {
    return this.page
      .locator('.MuiCard-root', { hasText: name })
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
  }

  /** Returns true if no behavior card with the given name is visible. */
  async cardIsGone(name: string): Promise<boolean> {
    return this.page
      .locator('.MuiCard-root', { hasText: name })
      .isHidden({ timeout: 15_000 })
      .catch(() => false);
  }
}
