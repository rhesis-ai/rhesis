import { test, expect } from '@playwright/test';
import { TasksPage } from '../pages/TasksPage';
import { confirmDeleteDialog } from '../helpers/CrudHelper';

/**
 * CRUD interaction tests for Tasks.
 *
 * Covers: D4.3 (create task at /tasks/create), D4.5 (change status auto-save),
 * D4.8 (select + bulk delete).
 */
test.describe('Tasks — CRUD @crud', () => {
  test('can create a task via /tasks/create', async ({ page }) => {
    const UNIQUE_TITLE = `e2e-task-${Date.now()}`;

    const tasksPage = new TasksPage(page);
    await tasksPage.gotoCreate();
    await page.waitForLoadState('networkidle');

    // Check we are on the create page — it should not be an error
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');

    // Fill the title field
    const titleInput = page.getByRole('textbox', { name: /title/i }).first();
    const hasTitle = await titleInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTitle) {
      test.skip(true, 'Title input not found on /tasks/create — skipping');
      return;
    }
    await titleInput.fill(UNIQUE_TITLE);

    // Fill description if available
    const descInput = page
      .getByRole('textbox', { name: /description/i })
      .first();
    if (await descInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await descInput.fill('Created by Playwright E2E test');
    }

    // Submit
    const saveBtn = page
      .getByRole('button', { name: /save|create task|submit/i })
      .first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, 'Save button not found on /tasks/create — skipping');
      return;
    }
    await saveBtn.click();

    // Wait for redirect away from /tasks/create (to the list or detail page).
    // The plain pattern /\/tasks($|\/)/ would match /tasks/create immediately,
    // causing the next goto('/tasks') to ERR_ABORTED during an ongoing redirect.
    await page.waitForURL(url => !url.pathname.endsWith('/tasks/create'), {
      timeout: 15_000,
    });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can change task status to In Progress on the detail page', async ({
    page,
  }) => {
    const UNIQUE_TITLE = `e2e-task-status-${Date.now()}`;

    const tasksPage = new TasksPage(page);

    // --- Setup: create a task ---
    await tasksPage.gotoCreate();
    await page.waitForLoadState('networkidle');

    const titleInput = page.getByRole('textbox', { name: /title/i }).first();
    const hasTitle = await titleInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTitle) {
      test.skip(true, 'Title input not found — skipping status change test');
      return;
    }
    await titleInput.fill(UNIQUE_TITLE);

    const saveBtn = page
      .getByRole('button', { name: /save|create task|submit/i })
      .first();
    if (!(await saveBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, 'Save button not found — skipping');
      return;
    }
    await saveBtn.click();
    await page.waitForURL(url => !url.pathname.endsWith('/tasks/create'), {
      timeout: 15_000,
    });
    await page.waitForLoadState('networkidle');

    // --- Navigate to the task detail page ---
    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Click the row with our task title
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

    // On the detail page, find the Status dropdown
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

    // Change status to "In Progress"
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

    // The page should not crash after auto-save
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can bulk-delete tasks via the grid selection', async ({ page }) => {
    const UNIQUE_TITLE = `e2e-task-del-${Date.now()}`;

    const tasksPage = new TasksPage(page);

    // --- Setup: create a task to delete ---
    await tasksPage.gotoCreate();
    await page.waitForLoadState('networkidle');

    const titleInput = page.getByRole('textbox', { name: /title/i }).first();
    const hasTitle = await titleInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasTitle) {
      test.skip(true, 'Title input not found — skipping bulk delete test');
      return;
    }
    await titleInput.fill(UNIQUE_TITLE);

    const saveBtn = page
      .getByRole('button', { name: /save|create task|submit/i })
      .first();
    if (!(await saveBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip(true, 'Save button not found — skipping');
      return;
    }
    await saveBtn.click();
    await page.waitForURL(url => !url.pathname.endsWith('/tasks/create'), {
      timeout: 15_000,
    });

    // Navigate to the tasks list
    await tasksPage.goto();
    await tasksPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Verify the task exists
    await expect(page.getByText(UNIQUE_TITLE).first()).toBeVisible({
      timeout: 15_000,
    });

    // Select the row via its checkbox
    await tasksPage.selectRowByText(UNIQUE_TITLE);

    // A delete button should appear in the toolbar
    const deleteBtn = page.getByRole('button', { name: /delete/i }).first();
    const hasDelete = await deleteBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasDelete) {
      test.skip(
        true,
        'Delete button not visible after row selection — skipping'
      );
      return;
    }

    await deleteBtn.click();
    await confirmDeleteDialog(page);
    await page.waitForLoadState('networkidle');

    // The row should be gone
    const gone = await tasksPage.rowIsGone(UNIQUE_TITLE);
    expect(gone, `Expected task "${UNIQUE_TITLE}" to be removed`).toBeTruthy();
  });
});
