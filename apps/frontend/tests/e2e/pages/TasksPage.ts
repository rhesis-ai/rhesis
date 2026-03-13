import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Tasks list page (/tasks).
 */
export class TasksPage extends BasePage {
  readonly dataGrid = this.page.locator('[role="grid"]');
  readonly createTaskButton = this.page
    .getByRole('button', { name: /create task/i })
    .first();

  constructor(page: Page) {
    super(page);
  }

  async goto() {
    await this.page.goto('/tasks');
  }

  async expectLoaded() {
    await expect(this.page).toHaveURL(/\/tasks/);
    await this.expectNoErrors();
  }

  /** Navigate directly to the task creation page. */
  async gotoCreate() {
    await this.page.goto('/tasks/create');
  }

  /** Returns true when the data grid is visible. */
  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Fill the Title field on the task creation form. */
  async fillTitle(title: string) {
    const titleInput = this.page
      .getByRole('textbox', { name: /title/i })
      .first();
    await titleInput.fill(title);
  }

  /** Fill the Description field on the task creation form. */
  async fillDescription(description: string) {
    const descInput = this.page
      .getByRole('textbox', { name: /description/i })
      .first();
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the task creation form. */
  async submitCreate() {
    const btn = this.page
      .getByRole('button', { name: /save|create task/i })
      .first();
    await btn.click();
  }

  /** Select a grid row containing the given text by clicking its checkbox. */
  async selectRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text });
    await row.locator('input[type="checkbox"]').click();
  }

  /** Click the bulk delete button (only visible when rows are selected). */
  async clickDeleteSelected() {
    await this.page.getByRole('button', { name: /delete/i }).click();
  }

  /** Click a row to navigate to the task detail page. */
  async clickRowByText(text: string) {
    await this.page.locator('[role="row"]', { hasText: text }).click();
  }

  /** Returns true if a row containing the given text is visible. */
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
