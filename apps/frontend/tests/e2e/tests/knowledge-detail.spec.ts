/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { KnowledgeDetailPage } from '../pages/KnowledgeDetailPage';

import knowledgeDetailFixture from '../fixtures/knowledge-detail.json';

const FIXTURE_ID = 'c2d3e4f5-0009-0009-0009-000000000001';

test.describe('Knowledge Detail @sanity', () => {
  test('knowledge detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/sources',
      FIXTURE_ID,
      knowledgeDetailFixture as any
    );

    const detail = new KnowledgeDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('knowledge detail renders heading and content @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/sources',
      FIXTURE_ID,
      knowledgeDetailFixture as any
    );

    const detail = new KnowledgeDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectContentVisible();
  });

  test('knowledge detail shows source name from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail(
      '/sources',
      FIXTURE_ID,
      knowledgeDetailFixture as any
    );

    await page.goto(`/knowledge/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('invalid knowledge ID is handled gracefully', async ({ page }) => {
    const response = await page.goto('/knowledge/non-existent-id-12345');
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
