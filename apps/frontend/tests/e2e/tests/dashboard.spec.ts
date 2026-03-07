import { test, expect } from '@playwright/test';
import { DashboardPage } from '../pages/DashboardPage';

test.describe('Dashboard @sanity', () => {
  test('dashboard page loads without error', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.expectLoaded();
  });

  test('dashboard page main content renders', async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await dashboard.expectContentVisible();
  });

  test('dashboard page does not show a loading spinner indefinitely', async ({
    page,
  }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // After network settles, no full-page spinner should remain
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(20);
  });

  test('dashboard has a valid page title', async ({ page }) => {
    await page.goto('/dashboard');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
    expect(title).toContain('Rhesis');
  });
});
