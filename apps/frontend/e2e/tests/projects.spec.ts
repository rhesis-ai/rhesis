import { test, expect } from '@playwright/test';
import { ProjectsPage } from '../pages/ProjectsPage';

test.describe('Projects @sanity', () => {
  test('projects page loads successfully', async ({ page }) => {
    const projects = new ProjectsPage(page);
    await projects.goto();
    await projects.expectLoaded();
  });

  test('projects page has expected content', async ({ page }) => {
    const projects = new ProjectsPage(page);
    await projects.goto();
    await projects.expectLoaded();
    await page.waitForLoadState('networkidle');

    // The page should contain project cards, empty state, or page content
    const hasProjects = await page.locator('.MuiCard-root').count();
    const hasEmptyState = await page.getByText(/no projects/i).count();
    const hasCreateButton = await page
      .getByRole('link', { name: /create/i })
      .or(page.getByRole('button', { name: /create/i }))
      .count();
    const hasPageContent = await page
      .locator('main, [role="main"]')
      .first()
      .isVisible()
      .catch(() => false);

    // At least one of these should be present
    expect(
      hasProjects + hasEmptyState + hasCreateButton + (hasPageContent ? 1 : 0)
    ).toBeGreaterThan(0);
  });
});
