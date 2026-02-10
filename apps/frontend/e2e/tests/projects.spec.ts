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

    // The page should contain either project cards or an empty state
    const hasProjects = await page.locator('[class*="ProjectCard"]').count();
    const hasEmptyState = await page.getByText(/no projects/i).count();
    const hasCreateButton = await page
      .getByRole('button', { name: /create|new/i })
      .count();

    // At least one of these should be present
    expect(hasProjects + hasEmptyState + hasCreateButton).toBeGreaterThan(0);
  });
});
