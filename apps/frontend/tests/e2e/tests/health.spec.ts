import { test, expect } from '@playwright/test';

test.describe('Health @sanity', () => {
  test('app loads and redirects authenticated user to dashboard', async ({
    page,
  }) => {
    await page.goto('/');
    // Authenticated users should be redirected to /architect
    await expect(page).toHaveURL(/\/architect/);
  });

  test('dashboard page renders without server errors', async ({ page }) => {
    await page.goto('/architect');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
    // Page title should include Rhesis
    await expect(page).toHaveTitle(/Rhesis/i);
  });

  test('the backend is reachable', async ({ request }) => {
    const backend = process.env.BACKEND_URL || 'http://localhost:8080';
    const response = await request.get(`${backend}/health`);
    expect(response.ok()).toBeTruthy();
  });
});
