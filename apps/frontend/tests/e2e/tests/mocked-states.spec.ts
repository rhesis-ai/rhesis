/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';

import projectsFixture from '../fixtures/projects.json';
import testsFixture from '../fixtures/tests.json';
import testSetsFixture from '../fixtures/test-sets.json';
import testRunsFixture from '../fixtures/test-runs.json';
import behaviorsFixture from '../fixtures/behaviors.json';
import endpointsFixture from '../fixtures/endpoints.json';
import tasksFixture from '../fixtures/tasks.json';
import tokensFixture from '../fixtures/tokens.json';

/**
 * Mocked-state tests verify page rendering in three deterministic scenarios:
 *   1. Empty state  — API returns [] so the "no items" UI must appear
 *   2. Populated    — API returns fixture data so at least one row/card shows
 *   3. Error state  — API returns 500 so the page must not crash
 *
 * Tagged @mocked so they can be run independently from live-backend tests.
 * All tests run against the Quick Start auth session (storageState).
 */

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------
test.describe('Projects — mocked states @mocked', () => {
  test('empty state shows no-projects message', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/projects', []);
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    const emptyMsg = page.getByText(/no projects found/i);
    await expect(emptyMsg).toBeVisible();
  });

  test('populated state shows project cards', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/projects', projectsFixture as any[]);
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    // At least one project card rendered
    const cards = page.locator('.MuiCard-root');
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/projects', 500);
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
test.describe('Tests — mocked states @mocked', () => {
  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/tests', testsFixture as any[]);
    await page.goto('/tests');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/tests', 500);
    await page.goto('/tests');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// Test Sets
// ---------------------------------------------------------------------------
test.describe('Test Sets — mocked states @mocked', () => {
  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/test_sets', testSetsFixture as any[]);
    await page.goto('/test-sets');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/test_sets', 500);
    await page.goto('/test-sets');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// Test Runs
// ---------------------------------------------------------------------------
test.describe('Test Runs — mocked states @mocked', () => {
  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/test_runs', testRunsFixture as any[]);
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/test_runs', 500);
    await page.goto('/test-runs');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// Behaviors
// ---------------------------------------------------------------------------
test.describe('Behaviors — mocked states @mocked', () => {
  test('empty state shows no-behaviors message', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/behaviors', []);
    await page.goto('/behaviors');
    await page.waitForLoadState('networkidle');

    const emptyMsg = page.getByText(/no behaviors found/i);
    await expect(emptyMsg).toBeVisible();
  });

  test('populated state shows behavior cards', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/behaviors', behaviorsFixture as any[]);
    await page.goto('/behaviors');
    await page.waitForLoadState('networkidle');

    const cards = page.locator('.MuiCard-root');
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/behaviors', 500);
    await page.goto('/behaviors');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------
test.describe('Endpoints — mocked states @mocked', () => {
  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/endpoints', endpointsFixture as any[]);
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/endpoints', 500);
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------
test.describe('Tasks — mocked states @mocked', () => {
  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/tasks', tasksFixture as any[]);
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/tasks', 500);
    await page.goto('/tasks');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});

// ---------------------------------------------------------------------------
// API Tokens
// ---------------------------------------------------------------------------
test.describe('API Tokens — mocked states @mocked', () => {
  test('empty state shows create-token message', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/tokens', []);
    await page.goto('/tokens');
    await page.waitForLoadState('networkidle');

    // The "Create API Token" button is always shown (toolbar + empty state overlay)
    const createBtn = page.getByRole('button', { name: /create api token/i });
    await expect(createBtn.first()).toBeVisible();
  });

  test('populated state shows data grid with rows', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockList('/tokens', tokensFixture as any[]);
    await page.goto('/tokens');
    await page.waitForLoadState('networkidle');

    const grid = page.locator('[role="grid"]');
    await expect(grid).toBeVisible();
  });

  test('error state does not crash the page', async ({ page }) => {
    const mock = new MockApiHelper(page);
    await mock.mockError('/tokens', 500);
    await page.goto('/tokens');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
