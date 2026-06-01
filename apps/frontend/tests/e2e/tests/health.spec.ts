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

  test('API base URL is reachable from the frontend', async ({ request }) => {
    // Verify the backend health endpoint responds
    const apiBase =
      process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
    const response = await request.get(`${apiBase}/health`);
    expect(response.ok()).toBeTruthy();
  });
});
