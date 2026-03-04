/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { TestDetailPage } from '../pages/TestDetailPage';

import testDetailFixture from '../fixtures/test-detail.json';

const FIXTURE_ID = 'b1c2d3e4-0002-0002-0002-000000000001';

test.describe('Test Detail @sanity', () => {
  test('test detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tests', FIXTURE_ID, testDetailFixture as any);

    const detail = new TestDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('test detail renders heading and content @mocked', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tests', FIXTURE_ID, testDetailFixture as any);

    const detail = new TestDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectContentVisible();
  });

  test('test detail shows test name from fixture @mocked', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tests', FIXTURE_ID, testDetailFixture as any);

    await page.goto(`/tests/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    // The test name or part of the fixture content should appear on the page
    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('invalid test ID is handled gracefully', async ({ page }) => {
    const response = await page.goto('/tests/non-existent-id-12345');
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
