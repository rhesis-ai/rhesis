import { test, expect } from '@playwright/test';
import { GenerationPage } from '../pages/GenerationPage';

test.describe('Generation @sanity', () => {
  test('generation page redirects to tests', async ({ page }) => {
    const generation = new GenerationPage(page);
    await generation.goto();
    await generation.expectRedirectedToTests();
  });

  test('generation redirect ends on a working page', async ({ page }) => {
    await page.goto('/generation');
    await page.waitForURL(/\/tests/, { timeout: 10_000 });

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');

    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
