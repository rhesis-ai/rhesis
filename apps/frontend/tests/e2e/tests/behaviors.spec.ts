import { test, expect } from '@playwright/test';
import { BehaviorsPage } from '../pages/BehaviorsPage';

test.describe('Behaviors @sanity', () => {
  test('behaviors page loads without error', async ({ page }) => {
    const behaviors = new BehaviorsPage(page);
    await behaviors.goto();
    await behaviors.expectLoaded();
  });

  test('behaviors page shows correct heading', async ({ page }) => {
    const behaviors = new BehaviorsPage(page);
    await behaviors.goto();
    await behaviors.expectLoaded();
    await behaviors.expectHeadingVisible();
  });

  test('behaviors page shows content or empty state', async ({ page }) => {
    const behaviors = new BehaviorsPage(page);
    await behaviors.goto();
    await behaviors.expectContentVisible();
  });

  test('behaviors page shows search bar', async ({ page }) => {
    const behaviors = new BehaviorsPage(page);
    await behaviors.goto();
    await behaviors.expectSearchBarVisible();
  });

  test('behaviors page has a valid page title', async ({ page }) => {
    await page.goto('/behaviors');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
