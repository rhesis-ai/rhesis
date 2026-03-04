import { test, expect } from '@playwright/test';
import { PlaygroundPage } from '../pages/PlaygroundPage';

test.describe('Playground @sanity', () => {
  test('playground page loads without error', async ({ page }) => {
    const playground = new PlaygroundPage(page);
    await playground.goto();
    await playground.expectLoaded();
  });

  test('playground page shows correct heading', async ({ page }) => {
    const playground = new PlaygroundPage(page);
    await playground.goto();
    await playground.expectLoaded();
    await playground.expectHeadingVisible();
  });

  test('playground page shows endpoint selector or no-endpoints message', async ({
    page,
  }) => {
    const playground = new PlaygroundPage(page);
    await playground.goto();
    await playground.expectContentVisible();
  });

  test('playground page has a valid page title', async ({ page }) => {
    await page.goto('/playground');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
