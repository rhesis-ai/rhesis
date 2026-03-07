import { test, expect } from '@playwright/test';
import { TestResultsPage } from '../pages/TestResultsPage';

test.describe('Test Results @sanity', () => {
  test('test results page loads without error', async ({ page }) => {
    const testResults = new TestResultsPage(page);
    await testResults.goto();
    await testResults.expectLoaded();
  });

  test('test results page shows correct heading', async ({ page }) => {
    const testResults = new TestResultsPage(page);
    await testResults.goto();
    await testResults.expectLoaded();
    await testResults.expectHeadingVisible();
  });

  test('test results page renders dashboard content', async ({ page }) => {
    const testResults = new TestResultsPage(page);
    await testResults.goto();
    await testResults.expectContentVisible();
  });

  test('test results page does not show loading spinner indefinitely', async ({
    page,
  }) => {
    await page.goto('/test-results');
    await page.waitForLoadState('networkidle');

    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(20);
  });

  test('test results page has a valid page title', async ({ page }) => {
    await page.goto('/test-results');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
