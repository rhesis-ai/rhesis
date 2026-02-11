import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

/**
 * Smoke tests that verify sidebar navigation links work correctly.
 * Each test clicks a sidebar item and asserts the URL changed.
 */
test.describe('Navigation @sanity', () => {
  test('can navigate to Projects from sidebar', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.expectLoaded();

    await dashboard.navigateTo('Projects');
    await expect(page).toHaveURL(/\/projects/);
  });

  test('can navigate to Test Sets from sidebar', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.expectLoaded();

    await dashboard.navigateTo('Test Sets');
    await expect(page).toHaveURL(/\/test-sets/);
  });

  test('can navigate to Endpoints from sidebar', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.expectLoaded();

    await dashboard.navigateTo('Endpoints');
    await expect(page).toHaveURL(/\/endpoints/);
  });

  test('can navigate back to Dashboard from another page', async ({ page }) => {
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/projects/);

    const dashboard = new DashboardPage(page);
    await dashboard.navigateTo('Dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
