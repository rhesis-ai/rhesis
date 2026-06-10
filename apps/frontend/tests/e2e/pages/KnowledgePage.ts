import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';
import {
  expectOpenDrawerTitle,
  openDrawer,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

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
    await expectOpenDrawerTitle(this.page, /^upload source$/i);
  }

  /**
   * Set the title field in the upload drawer.
   * The title may be pre-filled from the filename — this clears and refills it.
   */
  async setSourceTitle(title: string) {
    const titleInput = openDrawer(this.page)
      .getByRole('textbox', { name: /title/i })
      .first();
    await titleInput.clear();
    await titleInput.fill(title);
  }

  /** Set the description field in the upload drawer. */
  async setSourceDescription(description: string) {
    const descInput = openDrawer(this.page).getByRole('textbox', {
      name: /description/i,
    });
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the upload drawer and wait for the API response. */
  async submitUpload() {
    const uploadResponse = this.page.waitForResponse(
      resp =>
        resp.url().includes('/sources') &&
        resp.request().method() === 'POST' &&
        resp.ok(),
      { timeout: 30_000 }
    );
    await openDrawer(this.page)
      .getByRole('button', { name: /^upload source$/i })
      .click();
    await uploadResponse;
  }

  /** BaseDrawer stays mounted — wait for the drawer to close. */
  async waitForUploadDrawerClosed() {
    await waitForDrawerClosed(this.page, 20_000);
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    const row = this.page
      .locator('.MuiDataGrid-row')
      .filter({ hasText: text })
      .first();
    await row.scrollIntoViewIfNeeded();
    await row.hover();
    const deleteBtn = row.getByRole('button', { name: /^delete$/i });
    await expect(deleteBtn).toBeVisible({ timeout: 10_000 });
    await deleteBtn.click();
  }

  /** Returns true if a row containing the given text is visible in the grid. */
  async rowIsVisible(text: string): Promise<boolean> {
    return this.page
      .locator('.MuiDataGrid-row')
      .filter({ hasText: text })
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
  }

  /** Returns true if no row containing the given text is visible. */
  async rowIsGone(text: string): Promise<boolean> {
    return this.page
      .locator('.MuiDataGrid-row')
      .filter({ hasText: text })
      .isHidden({ timeout: 15_000 })
      .catch(() => false);
  }
}
