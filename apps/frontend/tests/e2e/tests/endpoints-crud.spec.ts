/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect, type Page } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import {
  expectGridRowVisible,
  waitForDrawerClosed,
} from '../helpers/CrudHelper';

import endpointsFixture from '../fixtures/endpoints.json';

/**
 * CRUD interaction tests for Endpoints.
 *
 * These tests exercise the new-endpoint wizard, verify field interaction, and
 * create an endpoint in the active (Quick Start) project.
 */

const nextButton = (page: Page) =>
  page.getByRole('button', { name: /^next$/i });

/** Fill the Overview step and move on to Connection. */
async function goToConnection(page: Page, name: string) {
  const nameField = page.locator('input[name="name"]');
  await expect(nameField).toBeVisible({ timeout: 15_000 });
  await nameField.fill(name);
  await nextButton(page).click();
}

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

    // Next stays disabled until the Overview step has a name.
    await expect(nextButton(page)).toBeDisabled();
    await goToConnection(page, UNIQUE_NAME);

    const urlField = page.locator('input[name="url"]');
    await expect(urlField).toBeVisible({ timeout: 15_000 });
    await urlField.fill(TEST_URL);
    await expect(urlField).toHaveValue(TEST_URL);

    // Earlier steps stay reachable; step panels unmount on switch, state is kept.
    await page.getByRole('button', { name: /basics/i }).click();
    await expect(page.locator('input[name="name"]')).toHaveValue(UNIQUE_NAME);
  });

  test('client credentials replaces the API token with OAuth fields', async ({
    page,
  }) => {
    await page.goto('/endpoints?create=1');
    await goToConnection(page, `e2e-endpoint-${Date.now()}`);
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

    // The target URL isn't reachable from CI, so the wizard's test calls get a canned reply.
    await page.route('**/endpoints/test', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ raw_response: { text: 'Hello from e2e' } }),
      })
    );

    // The create drawer uses the active project; it has no project field.
    await goToConnection(page, UNIQUE_NAME);
    await page.locator('input[name="url"]').fill(TEST_URL);
    await nextButton(page).click();

    // Mapping: send input as `prompt`; the test runs by itself, then map the reply to output.
    await page.getByLabel('API field for input').fill('prompt');
    await expect(page.getByText('Test request successful')).toBeVisible();
    await page.getByLabel('Response value for output').click();
    await page.getByRole('option', { name: '$.text' }).click();
    await nextButton(page).click();

    // Test: Create only unlocks after a passing run.
    const createButton = page.getByRole('button', {
      name: /^create endpoint$/i,
    });
    await expect(createButton).toBeDisabled();
    await page.getByRole('textbox', { name: 'Value for input' }).fill('Hello');
    await page.getByRole('button', { name: /send test request/i }).click();
    await expect(page.getByText('Endpoint is ready')).toBeVisible();
    await createButton.click();

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
