/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import {
  expectGridRowVisible,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

import endpointsFixture from '../fixtures/endpoints.json';

/**
 * CRUD interaction tests for Endpoints.
 *
 * These tests exercise the new-endpoint form, verify field interaction, and
 * create an endpoint in the active (Quick Start) project.
 */
test.describe('Endpoints — CRUD @crud', () => {
  test('new endpoint form loads and required fields are fillable', async ({
    page,
  }) => {
    const UNIQUE_NAME = `e2e-endpoint-${Date.now()}`;
    const TEST_URL = 'https://api.example.com/e2e-test';

    await page.goto('/endpoints?create=1');
    await expect(page).toHaveURL(/\/endpoints\/?$/);

    // Verify page loaded without errors
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');

    // Create page should show required fields.
    // name attributes on TextFields keep selectors stable for e2e.
    const nameField = page.locator('input[name="name"]');

    await expect(nameField).toBeVisible({ timeout: 15_000 });
    await nameField.fill(UNIQUE_NAME);

    // URL field is on the Connection tab
    await page.getByRole('tab', { name: /connection/i }).click();
    const urlField = page.locator('input[name="url"]');
    await expect(urlField).toBeVisible({ timeout: 15_000 });
    await urlField.fill(TEST_URL);

    // Verify URL value was accepted on the Connection tab
    await expect(urlField).toHaveValue(TEST_URL);

    // Switch back to Overview to verify the name field (tab panels unmount on switch)
    await page.getByRole('tab', { name: /overview/i }).click();
    await expect(nameField).toHaveValue(UNIQUE_NAME);
  });

  test('client credentials replaces the API token with OAuth fields', async ({
    page,
  }) => {
    await page.goto('/endpoints?create=1');
    await expect(page.locator('input[name="name"]')).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole('tab', { name: /connection/i }).click();
    await expect(page.getByLabel(/api token/i)).toBeVisible();

    await page.getByLabel('Authentication').click();
    await page.getByRole('option', { name: /client credentials/i }).click();

    await expect(page.getByLabel(/token url/i)).toBeVisible();
    await expect(page.getByLabel(/client id/i)).toBeVisible();
    await expect(page.getByLabel(/^client secret/i)).toHaveAttribute(
      'type',
      'password'
    );
    await expect(page.getByLabel(/api token/i)).toHaveCount(0);

    await page.getByLabel(/token url/i).fill('not a url');
    await expect(page.getByText('Enter a valid URL')).toBeVisible();
  });

  test('can create an endpoint in the active project', async ({ page }) => {
    const UNIQUE_NAME = `e2e-endpoint-${Date.now()}`;
    const TEST_URL = 'https://api.example.com/e2e-test';

    await page.goto('/endpoints?create=1');
    await expect(page).toHaveURL(/\/endpoints\/?$/);

    // The create drawer uses the active project; it has no project field.
    await page.locator('input[name="name"]').fill(UNIQUE_NAME);
    await page.getByRole('tab', { name: /connection/i }).click();
    await page.locator('input[name="url"]').fill(TEST_URL);
    await page.getByRole('button', { name: /^create endpoint$/i }).click();

    await waitForDrawerClosed(page, { timeout: 20_000 });
    await expectGridRowVisible(page, UNIQUE_NAME);
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
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
