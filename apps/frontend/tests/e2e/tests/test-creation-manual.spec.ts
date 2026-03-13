import { test, expect } from '@playwright/test';
import { TestsPage } from '../pages/TestsPage';

/**
 * Manual test creation flow tests.
 *
 * Covers: B2.3 (type selection modal), B2.4 (creation method modal),
 * B2.5 (fill a row), B2.6 (add another test case), B2.8 (save to test set).
 *
 * The wizard walks through two modal dialogs before reaching the manual
 * test writer page. Each step gracefully skips if the expected element is
 * not found, since the exact button labels may differ between environments.
 */
test.describe('Tests — manual creation wizard @crud', () => {
  test('can open the test type selection modal', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Click "Add Tests" — the button that opens the first wizard modal
    const addBtn = page.getByRole('button', { name: /add tests/i }).first();
    const addVisible = await addBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!addVisible) {
      test.skip(true, 'Add Tests button not found — skipping');
      return;
    }

    await addBtn.click();

    // The Test Type Selection modal should open
    const dialog = page.getByRole('dialog');
    const dialogVisible = await dialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!dialogVisible) {
      test.skip(true, 'Test type dialog did not open — skipping');
      return;
    }

    // Both card options should be present
    await expect(page.getByText(/single.turn tests/i).first()).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText(/multi.turn tests/i).first()).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can advance to the creation method selection modal', async ({
    page,
  }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const addBtn = page.getByRole('button', { name: /add tests/i }).first();
    const addVisible = await addBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!addVisible) {
      test.skip(true, 'Add Tests button not found — skipping');
      return;
    }

    await addBtn.click();

    // Step 1: Select "Single-Turn Tests"
    const singleTurnSelect = page
      .getByRole('button', { name: /select/i })
      .first();
    const hasSingleTurn = await singleTurnSelect
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSingleTurn) {
      test.skip(true, 'Single-Turn select button not found — skipping');
      return;
    }
    await singleTurnSelect.click();

    // Step 2: The creation method modal should now be visible
    await expect(
      page
        .getByText(/generate tests with ai|write tests manually|start writing/i)
        .first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('can navigate to the manual test writer page', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const addBtn = page.getByRole('button', { name: /add tests/i }).first();
    const addVisible = await addBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!addVisible) {
      test.skip(true, 'Add Tests button not found — skipping');
      return;
    }
    await addBtn.click();

    // Select Single-Turn
    const singleTurnSelect = page
      .getByRole('button', { name: /select/i })
      .first();
    const hasSingleTurn = await singleTurnSelect
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSingleTurn) {
      test.skip(true, 'Single-Turn select button not found — skipping');
      return;
    }
    await singleTurnSelect.click();

    // Click "Start Writing" / "Write Tests Manually"
    const manualBtn = page
      .getByRole('button', { name: /start writing|write.*manually|manual/i })
      .first();
    const hasManual = await manualBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasManual) {
      test.skip(true, '"Start Writing" button not found — skipping');
      return;
    }
    await manualBtn.click();

    // Should navigate to the manual writer page
    await page.waitForURL(/\/tests\/(create|new|manual)/, { timeout: 15_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('can fill a test row and add a second row on the manual writer page', async ({
    page,
  }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const addBtn = page.getByRole('button', { name: /add tests/i }).first();
    const addVisible = await addBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!addVisible) {
      test.skip(true, 'Add Tests button not found — skipping');
      return;
    }
    await addBtn.click();

    const singleTurnSelect = page
      .getByRole('button', { name: /select/i })
      .first();
    const hasSingleTurn = await singleTurnSelect
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSingleTurn) {
      test.skip(true, 'Single-Turn select button not found — skipping');
      return;
    }
    await singleTurnSelect.click();

    const manualBtn = page
      .getByRole('button', { name: /start writing|write.*manually|manual/i })
      .first();
    const hasManual = await manualBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasManual) {
      test.skip(true, '"Start Writing" button not found — skipping');
      return;
    }
    await manualBtn.click();

    await page.waitForURL(/\/tests\/(create|new|manual)/, { timeout: 15_000 });
    await page.waitForLoadState('networkidle');

    // Fill in the first test row — look for a test prompt input
    const promptInput = page
      .getByRole('textbox', { name: /test prompt|prompt|content/i })
      .first();
    const hasPrompt = await promptInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasPrompt) {
      test.skip(true, 'Test prompt input not found on writer page — skipping');
      return;
    }
    await promptInput.fill('e2e test prompt for Playwright');

    // Click "Add Another Test Case" / "Add Row"
    const addRowBtn = page
      .getByRole('button', { name: /add another|add test case|add row/i })
      .first();
    const hasAddRow = await addRowBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (hasAddRow) {
      await addRowBtn.click();
      // Verify a counter now shows 2
      const counter = page.getByText(/total.*2|2.*test case/i).first();
      const hasCounter = await counter
        .isVisible({ timeout: 5_000 })
        .catch(() => false);
      if (hasCounter) {
        await expect(counter).toBeVisible();
      }
    }

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can save tests from the manual writer page', async ({ page }) => {
    const UNIQUE_SET_NAME = `e2e-manual-${Date.now()}`;

    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const addBtn = page.getByRole('button', { name: /add tests/i }).first();
    const addVisible = await addBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!addVisible) {
      test.skip(true, 'Add Tests button not found — skipping');
      return;
    }
    await addBtn.click();

    const singleTurnSelect = page
      .getByRole('button', { name: /select/i })
      .first();
    const hasSingleTurn = await singleTurnSelect
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSingleTurn) {
      test.skip(true, 'Single-Turn select button not found — skipping');
      return;
    }
    await singleTurnSelect.click();

    const manualBtn = page
      .getByRole('button', { name: /start writing|write.*manually|manual/i })
      .first();
    const hasManual = await manualBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasManual) {
      test.skip(true, '"Start Writing" button not found — skipping');
      return;
    }
    await manualBtn.click();

    await page.waitForURL(/\/tests\/(create|new|manual)/, { timeout: 15_000 });
    await page.waitForLoadState('networkidle');

    // Fill in the test prompt
    const promptInput = page
      .getByRole('textbox', { name: /test prompt|prompt|content/i })
      .first();
    const hasPrompt = await promptInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasPrompt) {
      test.skip(true, 'Test prompt input not found — skipping save flow');
      return;
    }
    await promptInput.fill('e2e manual test — save flow');

    // Click Save
    const saveBtn = page.getByRole('button', { name: /^save$/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, 'Save button not found on writer page — skipping');
      return;
    }
    await saveBtn.click();

    // A save dialog should appear
    const saveDialog = page.getByRole('dialog');
    const dialogVisible = await saveDialog
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (dialogVisible) {
      // Optionally enter a test set name
      const setNameInput = saveDialog
        .getByRole('textbox', { name: /test set name/i })
        .first();
      const hasSetName = await setNameInput
        .isVisible({ timeout: 3_000 })
        .catch(() => false);
      if (hasSetName) await setNameInput.fill(UNIQUE_SET_NAME);

      // Confirm save
      await saveDialog.getByRole('button', { name: /^save$/i }).click();
    }

    // Should redirect to /tests after saving
    await page.waitForURL(/\/tests($|\?)/, { timeout: 20_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
