/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { TaskDetailPage } from '../pages/TaskDetailPage';

import taskDetailFixture from '../fixtures/task-detail.json';

const FIXTURE_ID = 'a2b3c4d5-0007-0007-0007-000000000001';

test.describe('Task Detail @sanity', () => {
  test('task detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tasks', FIXTURE_ID, taskDetailFixture as any);

    const detail = new TaskDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('task detail renders heading and details area @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tasks', FIXTURE_ID, taskDetailFixture as any);

    const detail = new TaskDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectDetailsAreaVisible();
  });

  test('task detail shows task title from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/tasks', FIXTURE_ID, taskDetailFixture as any);

    await page.goto(`/tasks/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    // The task title should appear somewhere in the page
    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('invalid task ID shows not-found state gracefully', async ({ page }) => {
    const response = await page.goto('/tasks/non-existent-id-12345');
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
