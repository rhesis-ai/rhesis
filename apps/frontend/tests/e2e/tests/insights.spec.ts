import { test, expect } from '@playwright/test';
import { InsightsPage } from '../pages/InsightsPage';

test.describe('Insights @sanity', () => {
  test('insights page loads without error', async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();
    await insights.expectLoaded();
  });

  test('insights page main content renders', async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();
    await insights.expectContentVisible();
  });

  test('legacy /dashboard redirects to insights', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/insights/, { timeout: 15_000 });
  });

  test('legacy /test-results redirects to insights', async ({ page }) => {
    await page.goto('/test-results');
    await expect(page).toHaveURL(/\/insights/, { timeout: 15_000 });
  });
});
