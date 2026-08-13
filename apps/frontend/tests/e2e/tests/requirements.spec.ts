import { test, expect } from '@playwright/test';
import { RequirementsPage } from '../pages/RequirementsPage';

test.describe('Requirements @sanity', () => {
  test('requirements page loads without error', async ({ page }) => {
    const requirements = new RequirementsPage(page);
    await requirements.goto();
    await requirements.expectLoaded();
  });

  test('requirements page shows correct heading', async ({ page }) => {
    const requirements = new RequirementsPage(page);
    await requirements.goto();
    await requirements.expectLoaded();
    await requirements.expectHeadingVisible();
  });

  test('requirements page shows content or empty state', async ({ page }) => {
    const requirements = new RequirementsPage(page);
    await requirements.goto();
    await requirements.expectContentVisible();
  });

  test('requirements page shows search bar', async ({ page }) => {
    const requirements = new RequirementsPage(page);
    await requirements.goto();
    await requirements.expectSearchBarVisible();
  });

  test('requirements page has a valid page title', async ({ page }) => {
    await page.goto('/requirements');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
