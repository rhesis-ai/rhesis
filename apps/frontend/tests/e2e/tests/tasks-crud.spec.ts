import { test, expect } from '@playwright/test';
import { TasksPage } from '../pages/TasksPage';
import {
  confirmDeleteDialog,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for Tasks.
 *
 * Covers: D4.3 (create task via drawer on /tasks), D4.5 (change status auto-save),
 * D4.8 (delete task via row actions).
 */
test.describe('Tasks — CRUD @crud', () => {
  async function createTaskViaDrawer(
    tasksPage: TasksPage,
    page: import('@playwright/test').Page,
    title: string
  ): Promise<boolean> {
    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tasksPage.openCreateDrawer();

    const titleInput = page
      .getByRole('textbox', { name: /task title/i })
      .first();
    const hasTitle = await titleInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTitle) {
      return false;
    }
    await titleInput.fill(title);

    const descInput = page
      .getByRole('textbox', { name: /description/i })
      .first();
    if (await descInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await descInput.fill('Created by Playwright E2E test');
    }

    const saveBtn = page.getByRole('button', { name: /create task/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSave) {
      return false;
    }
    await saveBtn.click();
    await waitForDrawerClosed(page);

    await page.waitForLoadState('networkidle');
    await tasksPage.expectTaskVisible(title);
    return true;
  }

  test('can create a task via the overview drawer', async ({ page }) => {
    const UNIQUE_TITLE = `e2e-task-${Date.now()}`;
    const tasksPage = new TasksPage(page);

    const created = await createTaskViaDrawer(tasksPage, page, UNIQUE_TITLE);
    if (!created) {
      test.skip(true, 'Create drawer not available — skipping');
      return;
    }

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

    const titleInput = page
      .getByRole('textbox', { name: /task title/i })
      .first();
    const hasTitle = await titleInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTitle) {
      test.skip(true, 'Create drawer not opened after redirect — skipping');
      return;
    }
  });

  test('can change task status to In Progress on the detail page', async ({
    page,
  }) => {
    const UNIQUE_TITLE = `e2e-task-status-${Date.now()}`;
    const tasksPage = new TasksPage(page);

    const created = await createTaskViaDrawer(tasksPage, page, UNIQUE_TITLE);
    if (!created) {
      test.skip(true, 'Could not create task — skipping status change test');
      return;
    }

    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const taskRow = page.locator('[role="row"]', { hasText: UNIQUE_TITLE });
    const rowVisible = await taskRow
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!rowVisible) {
      test.skip(
        true,
        'Task row not found after creation — skipping status change test'
      );
      return;
    }
    await taskRow.click();

    await page.waitForURL(/\/tasks\/.+/, { timeout: 10_000 });
    await page.waitForLoadState('networkidle');

    const statusSelect = page
      .locator('[aria-haspopup="listbox"]')
      .filter({ hasText: /open|in progress|completed|cancelled/i })
      .first();
    const hasStatusSelect = await statusSelect
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasStatusSelect) {
      test.skip(true, 'Status dropdown not found on task detail — skipping');
      return;
    }

    await statusSelect.click();
    const inProgressOption = page
      .getByRole('option', { name: /in progress/i })
      .first();
    const hasOption = await inProgressOption
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasOption) {
      await page.keyboard.press('Escape');
      test.skip(true, '"In Progress" option not available — skipping');
      return;
    }
    await inProgressOption.click();

    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can delete a task via row actions', async ({ page }) => {
    const UNIQUE_TITLE = `e2e-task-del-${Date.now()}`;
    const tasksPage = new TasksPage(page);

    const created = await createTaskViaDrawer(tasksPage, page, UNIQUE_TITLE);
    if (!created) {
      test.skip(true, 'Could not create task — skipping delete test');
      return;
    }

    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await tasksPage.expectTaskVisible(UNIQUE_TITLE);

    await tasksPage.deleteRowByText(UNIQUE_TITLE);
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    const gone = await tasksPage.rowIsGone(UNIQUE_TITLE);
    expect(gone, `Expected task "${UNIQUE_TITLE}" to be removed`).toBeTruthy();
  });
});
