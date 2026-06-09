import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';
import { waitForDrawerClosed } from '../helpers/CrudHelper';

/**
 * Page Object for the Knowledge (sources) page (/knowledge).
 */
export class KnowledgePage extends BasePage {
  readonly uploadButton = this.page.getByRole('button', {
    name: /upload source/i,
  });
  readonly dataGrid = this.page.locator('[role="grid"]');

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/knowledge');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/knowledge/);
    await this.expectNoErrors();
  }

  /** Returns true when the data grid is visible (at least one source exists). */
  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Open the "Upload Source" drawer. */
  async openUploadSourceDialog() {
    await this.uploadButton.click();
    await this.page
      .getByRole('presentation')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /**
   * Set the title field in the upload drawer.
   * The title may be pre-filled from the filename — this clears and refills it.
   */
  async setSourceTitle(title: string) {
    const titleInput = this.page
      .getByRole('presentation')
      .getByRole('textbox', { name: /title/i })
      .first();
    await titleInput.clear();
    await titleInput.fill(title);
  }

  /** Set the description field in the upload drawer. */
  async setSourceDescription(description: string) {
    const descInput = this.page
      .getByRole('presentation')
      .getByRole('textbox', { name: /description/i });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the upload drawer. */
  async submitUpload() {
    const submitBtn = this.page
      .getByRole('presentation')
      .getByRole('button', { name: /upload source/i })
      .last();
    await submitBtn.click();
  }

  /** BaseDrawer stays mounted — wait for the drawer to close. */
  async waitForUploadDrawerClosed() {
    await waitForDrawerClosed(this.page, 20_000);
  }

  /** Select a grid row that contains the given text by clicking its checkbox. */
  async selectRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text });
    await row.locator('input[type="checkbox"]').click();
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text }).first();
    await row.scrollIntoViewIfNeeded();
    await row.hover();
    await row.locator('.row-actions button').last().click();
  }

  /** Returns true if a row containing the given text is visible in the grid. */
  async rowIsVisible(text: string): Promise<boolean> {
    return this.page
      .locator('[role="row"]', { hasText: text })
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
  }

  /** Returns true if no row containing the given text is visible. */
  async rowIsGone(text: string): Promise<boolean> {
    return this.page
      .locator('[role="row"]', { hasText: text })
      .isHidden({ timeout: 15_000 })
      .catch(() => false);
  }
}
