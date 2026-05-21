import { test, expect } from '@playwright/test';
import { InsightsPage } from '../pages/InsightsPage';

/**
 * Smoke tests that verify sidebar navigation links work correctly.
 * Each test clicks a sidebar item and asserts the URL changed.
 */
test.describe('Navigation @sanity', () => {
  test('can navigate to Projects from sidebar', async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();
    await insights.expectLoaded();

    await insights.navigateTo('Projects');
    await expect(page).toHaveURL(/\/projects/);
  });

  test('can navigate to Test Set from sidebar', async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();
    await insights.expectLoaded();

    await insights.navigateTo('Test Set');
    await expect(page).toHaveURL(/\/test-sets/);
  });

  test('can navigate to Endpoints from sidebar', async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();
    await insights.expectLoaded();

    await insights.navigateTo('Endpoints');
    await expect(page).toHaveURL(/\/endpoints/);
  });

  test('can navigate back to Insights from another page', async ({ page }) => {
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/projects/);

    const insights = new InsightsPage(page);
    await insights.navigateTo('Insights');
    await expect(page).toHaveURL(/\/insights/);
  });
});
