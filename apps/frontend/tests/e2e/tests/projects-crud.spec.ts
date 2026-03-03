import { test, expect } from '@playwright/test';

/**
 * CRUD interaction tests for Projects.
 *
 * These tests exercise the multi-step project creation wizard and verify
 * the project is accessible after creation.
 */
test.describe('Projects — CRUD @crud', () => {
  test('can create a project via the creation wizard', async ({ page }) => {
    const UNIQUE_NAME = `e2e-proj-${Date.now()}`;

    await page.goto('/projects/create-new');
    await page.waitForLoadState('networkidle');

    // Verify we are on the create project page
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Step 0: Project Details
    // Fill Project Name (required)
    await page.getByLabel('Project Name').fill(UNIQUE_NAME);

    // Fill Description (required)
    await page
      .getByLabel('Description')
      .fill('Created by Playwright CRUD test');

    // Click Continue to advance to the review step
    await page.getByRole('button', { name: /continue/i }).click();

    // Step 1: Finish / Review — verify the project name is shown in the summary
    await expect(page.getByText(UNIQUE_NAME)).toBeVisible({ timeout: 10_000 });

    // Click "Create Project"
    await page.getByRole('button', { name: /create project/i }).click();

    // After creation we should navigate to the project detail page or back to /projects
    await page.waitForURL(/\/projects/, { timeout: 20_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
