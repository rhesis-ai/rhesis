import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';
import { deleteGridRowByText, openDrawer } from '../helpers/CrudHelper';

/**
 * Page Object for the Tasks list page (/tasks).
 */
export class TasksPage extends BasePage {
  readonly dataGrid = this.page.locator('[role="grid"]');
  readonly newTaskFab = this.page.getByRole('button', { name: /new task/i });

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

  /** Open the create-task drawer via FAB or empty-state action. */
  async openCreateDrawer() {
    const fab = this.newTaskFab.first();
    const fabVisible = await fab
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (fabVisible) {
      await fab.click();
    } else {
      const emptyAction = this.page
        .getByRole('button', { name: /create task/i })
        .first();
      await emptyAction.click();
    }

    const drawer = openDrawer(this.page);
    await drawer
      .getByRole('textbox', { name: /task title/i })
      .waitFor({ state: 'visible', timeout: 10_000 });
    await this.page
      .waitForResponse(resp => resp.url().includes('/status') && resp.ok(), {
        timeout: 15_000,
      })
      .catch(() => null);
  }

  /**
   * Navigate via legacy /tasks/create URL (redirects to overview drawer).
   */
  async gotoCreate() {
    await this.page.goto('/tasks/create');
    await this.page.waitForURL(/\/tasks/, { timeout: 15_000 });
    await this.page.waitForLoadState('networkidle');
  }

  /** Returns true when the data grid is visible. */
  async hasDataGrid(): Promise<boolean> {
    return this.dataGrid.isVisible().catch(() => false);
  }

  /** Fill the Title field in the create drawer. */
  async fillTitle(title: string) {
    const titleInput = this.page
      .getByRole('textbox', { name: /title/i })
      .first();
    await titleInput.fill(title);
  }

  /** Fill the Description field in the create drawer. */
  async fillDescription(description: string) {
    const descInput = this.page
      .getByRole('textbox', { name: /description/i })
      .first();
    const visible = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (visible) await descInput.fill(description);
  }

  /** Submit the create drawer form. */
  async submitCreate() {
    const btn = this.page.getByRole('button', { name: /create task/i }).first();
    await btn.click();
  }

  /** Select a grid row containing the given text by clicking its checkbox. */
  async selectRowByText(text: string) {
    const row = this.page.locator('[role="row"]', { hasText: text });
    await row.locator('input[type="checkbox"]').click();
  }

  /** Delete a row via the hover-revealed row-actions delete icon. */
  async deleteRowByText(text: string) {
    await deleteGridRowByText(this.page, text);
  }

  /** Wait until a created task title appears in the grid or page body. */
  async expectTaskVisible(title: string) {
    await expect(this.page.getByText(title).first()).toBeVisible({
      timeout: 15_000,
    });
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
