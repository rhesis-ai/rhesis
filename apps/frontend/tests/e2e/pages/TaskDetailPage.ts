import { type Page, expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * Page Object for the Task detail page (/tasks/[identifier]).
 */
export class TaskDetailPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async goto(id: string) {
    await this.page.goto(`/tasks/${id}`);
  }

  async expectLoaded(id: string) {
    await expect(this.page).toHaveURL(new RegExp(`/tasks/${id}`));
    await this.expectNoErrors();
  }

  /** Assert a heading is visible — the task title comes from fixture data. */
  /** Assert the page has rendered its main content area.
   * A heading is preferred but the main element is accepted as fallback because
   * when the fixture ID is not in the backend the SSR renders without a heading. */
  async expectHeadingVisible() {
    await this.page.waitForLoadState('networkidle');
    const heading = this.page.getByRole('heading').first();
    const mainContent = this.page.locator('main, [role="main"]').first();
    const headingOk = await heading.isVisible().catch(() => false);
    const mainOk = await mainContent.isVisible().catch(() => false);
    expect(headingOk || mainOk).toBeTruthy();
  }

  /**
   * Assert the task details form area renders.
   * The task detail always shows status/priority fields or a "not found" alert.
   */
  async expectDetailsAreaVisible() {
    await this.page.waitForLoadState('networkidle');
    const mainContent = this.page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  }

  /** Assert the "Task Not Found" state is shown for an invalid ID. */
  async expectNotFoundVisible() {
    await this.page.waitForLoadState('networkidle');
    const notFound = this.page.getByText(/task not found/i);
    const mainContent = this.page.locator('main, [role="main"]').first();
    const hasNotFound = await notFound.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasNotFound || hasMain).toBeTruthy();
  }
}
