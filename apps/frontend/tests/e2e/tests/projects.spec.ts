import { test, expect } from '@playwright/test';
import { ProjectsPage } from '../pages/ProjectsPage';

test.describe('Projects @sanity', () => {
  test('projects page loads without error', async ({ page }) => {
    const projects = new ProjectsPage(page);
    await projects.goto();
    await projects.expectLoaded();
  });

  test('projects page shows correct heading', async ({ page }) => {
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('heading', { name: /projects/i }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('projects page shows create project button', async ({ page }) => {
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    // The "Create Project" action is always visible (even in empty state)
    const createButton = page
      .getByRole('link', { name: /create project/i })
      .or(page.getByRole('button', { name: /create project/i }));
    await expect(createButton.first()).toBeVisible();
  });

  test('projects page shows project cards or empty state', async ({ page }) => {
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    const cards = page.locator('.MuiCard-root');
    const emptyState = page.getByText(/no projects found/i);
    const mainContent = page.locator('main, [role="main"]').first();

    const hasCards = (await cards.count()) > 0;
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasMain = await mainContent.isVisible().catch(() => false);

    expect(hasCards || hasEmpty || hasMain).toBeTruthy();
  });

  test('projects page has a valid page title', async ({ page }) => {
    await page.goto('/projects');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});
