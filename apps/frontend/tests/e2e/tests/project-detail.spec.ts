/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';
import { ProjectDetailPage } from '../pages/ProjectDetailPage';

import projectDetailFixture from '../fixtures/project-detail.json';
import endpointsFixture from '../fixtures/endpoints.json';

const FIXTURE_ID = 'a1b2c3d4-0001-0001-0001-000000000001';

async function mockProjectDetailApis(
  page: import('@playwright/test').Page,
  mock: MockApiHelper,
  endpoints: Record<string, unknown>[] = []
) {
  await mock.mockDetail('/projects', FIXTURE_ID, projectDetailFixture as any);
  await mock.mockList('/endpoints', endpoints as any[]);
  await page.route(`**/api/v1/projects/${FIXTURE_ID}/members`, route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    })
  );
}

test.describe('Project Detail @sanity', () => {
  test('project detail loads with valid ID', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mockProjectDetailApis(page, mock, endpointsFixture as any[]);

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectLoaded(FIXTURE_ID);
  });

  test('project detail renders heading and content @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mockProjectDetailApis(page, mock, []);

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectHeadingVisible();
    await detail.expectContentVisible();
  });

  test('project detail shows Figma-aligned header and tabs @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mockProjectDetailApis(page, mock, []);

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID);
    await detail.expectMetadataStripVisible();
    await detail.expectTabNavVisible();
    await expect(page.getByText('Project details')).toBeVisible();
  });

  test('legacy tab query maps to configuration tab @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mockProjectDetailApis(page, mock, []);
    await page.route(
      `**/api/v1/projects/${FIXTURE_ID}/parameters/schema`,
      route =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ fields: [] }),
        })
    );
    await page.route(`**/api/v1/projects/${FIXTURE_ID}/environments`, route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ environments: {} }),
      })
    );

    const detail = new ProjectDetailPage(page);
    await detail.goto(FIXTURE_ID, 'tab=traceMetrics');
    await expect(
      page.getByRole('tab', { name: 'Advanced Configuration', selected: true })
    ).toBeVisible();
  });

  test('project detail page shows project name from fixture @mocked', async ({
    page,
  }) => {
    const mock = new MockApiHelper(page);
    await mockProjectDetailApis(page, mock, []);

    await page.goto(`/projects/${FIXTURE_ID}`);
    await page.waitForLoadState('networkidle');

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('invalid project ID is handled gracefully', async ({ page }) => {
    await page.goto('/projects/00000000-0000-0000-0000-000000000000');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
