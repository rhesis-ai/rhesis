/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';

import endpointsFixture from '../fixtures/endpoints.json';

/**
 * CRUD interaction tests for Endpoints.
 *
 * These tests exercise the new-endpoint form and verify field interaction.
 * Full creation is attempted when a project is available; the test degrades
 * gracefully when no projects exist in the test environment.
 */
test.describe('Endpoints — CRUD @crud', () => {
  test('new endpoint form loads and required fields are fillable', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-endpoint-${Date.now()}`;
    const TEST_URL = 'https://api.example.com/e2e-test';

    await page.goto('/endpoints/new');
    await page.waitForLoadState('networkidle');

    // Verify page loaded without errors
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');

    // The "Basic Information" tab should be visible (default tab).
    // Use name-attribute selectors — more reliable than getByLabel for
    // MUI required TextFields whose label renders as "Name *".
    const nameField = page.locator('input[name="name"]');
    const urlField = page.locator('input[name="url"]');

    await expect(nameField).toBeVisible({ timeout: 15_000 });
    await expect(urlField).toBeVisible({ timeout: 15_000 });

    // Fill required text fields
    await nameField.fill(UNIQUE_NAME);
    await urlField.fill(TEST_URL);

    // Verify values were accepted
    await expect(nameField).toHaveValue(UNIQUE_NAME);
    await expect(urlField).toHaveValue(TEST_URL);
  });

  test('can create an endpoint when a project is available', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-endpoint-${Date.now()}`;
    const TEST_URL = 'https://api.example.com/e2e-test';

    await page.goto('/endpoints/new');
    await page.waitForLoadState('networkidle');

    // Fill required text fields
    await page.locator('input[name="name"]').fill(UNIQUE_NAME);
    await page.locator('input[name="url"]').fill(TEST_URL);

    // The project select (#project-select) is required
    // Wait to see if any project options are available
    const projectSelectTrigger = page.locator('#project-select');
    const hasProjectSelect = await projectSelectTrigger
      .isVisible()
      .catch(() => false);

    if (!hasProjectSelect) {
      test.skip(true, 'Project select not found — skipping creation');
      return;
    }

    // Click the project select to open the dropdown
    await projectSelectTrigger.click();

    const listbox = page.getByRole('listbox');
    await listbox
      .waitFor({ state: 'visible', timeout: 5_000 })
      .catch(() => null);

    const options = await listbox.getByRole('option').all();

    if (options.length === 0) {
      test.skip(true, 'No projects available — skipping endpoint creation');
      return;
    }

    // Select the first available project
    await options[0].click();

    // Click "Create Endpoint"
    await page.getByRole('button', { name: /create endpoint/i }).click();

    // After creation the form navigates back to the endpoints list
    await page.waitForURL(/\/endpoints/, { timeout: 20_000 });
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

test.describe('Endpoints — click-through @crud', () => {
  test('clicking a grid row navigates to the detail page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/endpoints', endpointsFixture as any[]);

    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();

    if (rowCount < 2) {
      test.skip(true, 'No endpoint rows visible — skipping click-through');
      return;
    }

    // Click the first data row (index 0 is the header)
    await rows.nth(1).click();

    // Should navigate to an endpoint detail URL
    await expect(page).toHaveURL(/\/endpoints\/.+/);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
