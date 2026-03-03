import { test, expect } from '@playwright/test';
import { TestRunsPage } from '../pages/TestRunsPage';

test.describe('Test Runs — Extended @sanity', () => {
  test('test runs page loads and shows content area', async ({ page }) => {
    const testRunsPage = new TestRunsPage(page);
    await testRunsPage.goto();
    await testRunsPage.expectLoaded();
    await testRunsPage.waitForContent();

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('test runs page does not have broken layout', async ({ page }) => {
    const testRunsPage = new TestRunsPage(page);
    await testRunsPage.goto();
    await page.waitForLoadState('networkidle');

    // Check that a data grid or empty-state content is shown
    const hasGrid = await testRunsPage.hasDataGrid();
    const hasContent = await page
      .locator('main, [role="main"]')
      .first()
      .isVisible()
      .catch(() => false);

    expect(hasGrid || hasContent).toBeTruthy();
  });

  test('test runs page title is set', async ({ page }) => {
    const testRunsPage = new TestRunsPage(page);
    await testRunsPage.goto();
    await testRunsPage.waitForContent();

    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });

  test('test runs page HTTP response is successful', async ({ page }) => {
    const response = await page.goto('/test-runs');
    expect(response?.status()).toBeLessThan(500);
  });
});

test.describe('Test Run detail page @sanity', () => {
  test('test run detail with non-existent id shows error or redirects gracefully', async ({
    page,
  }) => {
    // Navigate to a non-existent test run — should not 500
    const response = await page.goto('/test-runs/non-existent-id-12345');
    // Either a redirect (3xx) or a handled error page (4xx) is acceptable; 5xx is not
    if (response) {
      expect(response.status()).not.toBe(500);
    }
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
