/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { TestRunDetailPage } from '../pages/TestRunDetailPage';

import testRunDetailFixture from '../fixtures/test-run-detail.json';
import testResultsFixture from '../fixtures/test-results.json';

const FIXTURE_ID = 'd1e2f3a4-0004-0004-0004-000000000001';

test.describe('Test Run Detail @sanity', () => {
  test('test run detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/test_runs',
      FIXTURE_ID,
      testRunDetailFixture as any
    );
    await mock.mockList('/test_results', []);

    const detail = new TestRunDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('test run detail renders heading and results area @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/test_runs',
      FIXTURE_ID,
      testRunDetailFixture as any
    );
    await mock.mockList('/test_results', testResultsFixture as any[]);

    const detail = new TestRunDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectResultsAreaVisible();
  });

  test('test run detail shows run name from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/test_runs',
      FIXTURE_ID,
      testRunDetailFixture as any
    );
    await mock.mockList('/test_results', []);

    await page.goto(`/test-runs/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Run #1 — Safety Test Set')).toBeVisible();
  });

  test('invalid test run ID is handled gracefully', async ({ page }) => {
    const response = await page.goto('/test-runs/non-existent-id-12345');
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
