import { test, expect } from '@playwright/test';

/**
 * Parameterized smoke test that verifies every protected route loads
 * without a server error. Acts as a baseline safety net — if a new page
 * is added to the list it is automatically covered.
 *
 * Tagged @sanity so it runs in CI alongside the other smoke tests.
 */

const protectedRoutes = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/projects', name: 'Projects' },
  { path: '/knowledge', name: 'Knowledge' },
  { path: '/behaviors', name: 'Behaviors' },
  { path: '/generation', name: 'Generation' },
  { path: '/playground', name: 'Playground' },
  { path: '/tests', name: 'Tests' },
  { path: '/test-sets', name: 'Test Sets' },
  { path: '/test-results', name: 'Test Results' },
  { path: '/test-runs', name: 'Test Runs' },
  { path: '/traces', name: 'Traces' },
  { path: '/tasks', name: 'Tasks' },
  { path: '/endpoints', name: 'Endpoints' },
  { path: '/tokens', name: 'API Tokens' },
];

test.describe('Page Smoke @sanity', () => {
  for (const route of protectedRoutes) {
    test(`${route.name} (${route.path}) loads without error`, async ({
      page,
    }) => {
      const response = await page.goto(route.path);

      // The HTTP response should be successful (not 500, 502, etc.)
      expect(response?.status()).toBeLessThan(500);

      // Page body should not contain server error messages
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
      await expect(page.locator('body')).not.toContainText('Application error');

      // The page should have a title (not blank)
      const title = await page.title();
      expect(title.length).toBeGreaterThan(0);
    });
  }
});
