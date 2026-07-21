import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';
import {
  deleteGridRowByText,
  expectOpenDrawerTitle,
  openDrawer,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

/**
 * Page Object for the Knowledge (sources) page (/knowledge).
 */
export class KnowledgePage extends BasePage {
  /** Page FAB — distinct from the empty-state "Upload source" CTA. */
  readonly uploadFabButton = this.page.getByRole('button', {
    name: 'Upload Source',
    exact: true,
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
    await this.uploadFabButton.click();
    await expectOpenDrawerTitle(this.page, /^upload source$/i);
  }

  /** Attach a file in the upload drawer and wait for the UI to reflect it. */
  async selectUploadFile(filePath: string) {
    const fileName = filePath.split('/').pop() ?? filePath;
    const drawer = openDrawer(this.page);
    const fileInput = drawer.locator('input[type="file"]');
    await expect(fileInput).toBeAttached({ timeout: 5_000 });
    await fileInput.setInputFiles(filePath);
    await expect(drawer.getByText(fileName)).toBeVisible({ timeout: 5_000 });
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
    const drawer = openDrawer(this.page);
    const saveButton = drawer.getByRole('button', {
      name: /^upload source$/i,
    });
    await expect(saveButton).toBeEnabled({ timeout: 10_000 });

    const uploadResponse = this.page.waitForResponse(
      resp =>
        resp.url().includes('/sources/upload') &&
        resp.request().method() === 'POST',
      { timeout: 60_000 }
    );
    await saveButton.click();
    const response = await uploadResponse;
    if (!response.ok()) {
      const body = await response.text().catch(() => '');
      throw new Error(`Upload failed (${response.status()}): ${body}`);
    }
  }

  /** BaseDrawer stays mounted — wait for the drawer to close. */
  async waitForUploadDrawerClosed() {
    await waitForDrawerClosed(this.page, 20_000);
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    await deleteGridRowByText(this.page, text);
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
