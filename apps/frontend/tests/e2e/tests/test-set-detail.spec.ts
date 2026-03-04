/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { TestSetDetailPage } from '../pages/TestSetDetailPage';

import testSetDetailFixture from '../fixtures/test-set-detail.json';
import testsFixture from '../fixtures/tests.json';

const FIXTURE_ID = 'c1d2e3f4-0003-0003-0003-000000000001';

test.describe('Test Set Detail @sanity', () => {
  test('test set detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    // Test sets are fetched via a filtered list query
    await mock.mockList('/test_sets', [testSetDetailFixture as any]);
    await mock.mockList('/tests', []);

    const detail = new TestSetDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('test set detail renders heading and tests grid @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/test_sets', [testSetDetailFixture as any]);
    await mock.mockList('/tests', testsFixture as any[]);

    const detail = new TestSetDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectTestsGridVisible();
  });

  test('test set detail shows set name from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/test_sets', [testSetDetailFixture as any]);
    await mock.mockList('/tests', []);

    await page.goto(`/test-sets/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Safety Test Set')).toBeVisible();
  });

  test('invalid test set ID is handled gracefully', async ({ page }) => {
    const response = await page.goto('/test-sets/non-existent-id-12345');
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
