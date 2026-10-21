import { test, expect, type Page } from '@playwright/test';
import { TasksPage } from '../pages/TasksPage';
import {
  confirmDeleteDialog,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for Tasks.
 *
 * Covers: D4.3 (create task via drawer on /tasks), D4.5 (change status from the
 * detail page), D4.8 (delete task via row actions).
 */
test.describe('Tasks — CRUD @crud', () => {
  async function createTaskViaDrawer(
    tasksPage: TasksPage,
    page: Page,
    title: string
  ) {
    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await tasksPage.openCreateDrawer();

    await page
      .getByRole('textbox', { name: /task title/i })
      .first()
      .fill(title);
    await page
      .getByRole('textbox', { name: /description/i })
      .first()
      .fill('Created by Playwright E2E test');

    // Save stays disabled until the drawer has loaded the task statuses.
    const saveBtn = page.getByRole('button', { name: /create task/i }).first();
    await expect(saveBtn).toBeEnabled({ timeout: 15_000 });
    await saveBtn.click();
    await waitForDrawerClosed(page, { timeout: 20_000 });

    await tasksPage.expectTaskVisible(title);
  }

  test('can create a task via the overview drawer', async ({ page }) => {
    await createTaskViaDrawer(
      new TasksPage(page),
      page,
      `e2e-task-${Date.now()}`
    );
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('legacy /tasks/create redirects and opens create flow', async ({
    page,
  }) => {
    const tasksPage = new TasksPage(page);
    await tasksPage.gotoCreate();

    await expect(page).toHaveURL(/\/tasks/);
    await expect(page).not.toHaveURL(/\/tasks\/create$/);
    await expect(
      page.getByRole('textbox', { name: /task title/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('can change task status to In Progress on the detail page', async ({
    page,
  }) => {
    // Creates, opens, edits and reloads a task; first visits compile routes.
    test.slow();
    const UNIQUE_TITLE = `e2e-task-status-${Date.now()}`;
    const tasksPage = new TasksPage(page);
    await createTaskViaDrawer(tasksPage, page, UNIQUE_TITLE);

    await page.locator('[role="row"]', { hasText: UNIQUE_TITLE }).click();
    await page.waitForURL(/\/tasks\/.+/, { timeout: 10_000 });

    // The details are read-only until Edit; the status is then a select.
    const main = page.locator('main');
    await main.getByRole('button', { name: /^edit$/i }).click();
    await main
      .getByRole('combobox')
      .filter({ hasText: /^open$/i })
      .click();
    await page.getByRole('option', { name: /^in progress$/i }).click();
    const saved = page.waitForResponse(
      r =>
        r.request().method() === 'PATCH' &&
        r.url().includes('/tasks/') &&
        r.ok()
    );
    await main.getByRole('button', { name: /^save$/i }).click();
    await saved;

    await page.reload();
    await expect(main.getByText(/^in progress$/i).first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test('can delete a task via row actions', async ({ page }) => {
    const UNIQUE_TITLE = `e2e-task-del-${Date.now()}`;
    const tasksPage = new TasksPage(page);
    await createTaskViaDrawer(tasksPage, page, UNIQUE_TITLE);

    await tasksPage.deleteRowByText(UNIQUE_TITLE);
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    const gone = await tasksPage.rowIsGone(UNIQUE_TITLE);
    expect(gone, `Expected task "${UNIQUE_TITLE}" to be removed`).toBeTruthy();
  });
});
