import { test, expect } from '@playwright/test';
import { TestsPage } from '../pages/TestsPage';

test.describe('Tests @sanity', () => {
  test('tests page loads successfully', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.expectLoaded();
  });

  test('tests page shows grid or page content', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.waitForContent();

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('tests page has the correct page title', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();
    await testsPage.waitForContent();

    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });

  test('tests page does not show loading spinner indefinitely', async ({ page }) => {
    const testsPage = new TestsPage(page);
    await testsPage.goto();

    // Wait for network to settle — ensure no infinite loading
    await page.waitForLoadState('networkidle');

    // The loading text "Loading..." should not be the only thing visible
    const bodyText = await page.locator('body').innerText();
    // Page should have content beyond just "Loading..."
    expect(bodyText.length).toBeGreaterThan(10);
  });
});

test.describe('Tests navigation @sanity', () => {
  test('can navigate from dashboard to tests', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Navigate via sidebar link
    const testNavLink = page.locator('nav').getByRole('link', { name: /^tests$/i }).first();
    await testNavLink.click();

    await expect(page).toHaveURL(/\/tests/);
    await expect(page.locator('body')).not.toContainText('Internal Server Error');
  });

  test('tests URL shows correct route structure', async ({ page }) => {
    await page.goto('/tests');
    await expect(page).toHaveURL(/\/tests$/);
  });
});
