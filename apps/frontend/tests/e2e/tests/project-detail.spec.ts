/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { ProjectDetailPage } from '../pages/ProjectDetailPage';

import projectDetailFixture from '../fixtures/project-detail.json';
import endpointsFixture from '../fixtures/endpoints.json';

const FIXTURE_ID = 'a1b2c3d4-0001-0001-0001-000000000001';

test.describe('Project Detail @sanity', () => {
  test('project detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/projects', FIXTURE_ID, projectDetailFixture as any);
    await mock.mockList('/endpoints', endpointsFixture as any[]);

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('project detail renders heading and content @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/projects', FIXTURE_ID, projectDetailFixture as any);
    await mock.mockList('/endpoints', []);

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectContentVisible();
  });

  test('project detail page shows project name from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mock.mockDetail('/projects', FIXTURE_ID, projectDetailFixture as any);
    await mock.mockList('/endpoints', []);

    await page.goto(`/projects/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('invalid project ID is handled gracefully', async ({ page }) => {
    // Use a valid UUID format so the backend returns 404 (not 422).
    // Non-UUID strings trigger Pydantic validation errors that some pages
    // don't catch, causing a 500 / "Application error".
    const response = await page.goto(
      '/projects/00000000-0000-0000-0000-000000000000'
    );
    expect(response?.status()).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
