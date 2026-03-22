import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

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

  /** Open the "Upload Source" dialog/drawer. */
  async openUploadSourceDialog() {
    await this.uploadButton.click();
    await this.page
      .getByRole('dialog')
      .waitFor({ state: 'visible', timeout: 10_000 });
  }

  /**
   * Set the title field in the upload dialog.
   * The title may be pre-filled from the filename — this clears and refills it.
   */
  async setSourceTitle(title: string) {
    const titleInput = this.page
      .getByRole('dialog')
      .getByRole('textbox', { name: /title/i })
      .first();
    await titleInput.clear();
    await titleInput.fill(title);
  }

  /** Set the description field in the upload dialog. */
  async setSourceDescription(description: string) {
    const descInput = this.page
      .getByRole('dialog')
      .getByRole('textbox', { name: /description/i });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the upload dialog. */
  async submitUpload() {
    const submitBtn = this.page
      .getByRole('dialog')
      .getByRole('button', { name: /upload source|save|submit/i })
      .first();
    await submitBtn.click();
  }

  /** Select a grid row that contains the given text by clicking its checkbox. */
  async selectRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text });
    await row.locator('input[type="checkbox"]').click();
  }

  /** Click the "Delete Sources" toolbar button (visible only when rows are selected). */
  async clickDeleteSelected() {
    await this.page.getByRole('button', { name: /delete sources/i }).click();
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
