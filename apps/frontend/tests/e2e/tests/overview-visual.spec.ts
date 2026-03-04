/* eslint-disable @typescript-eslint/no-explicit-any */
import { test, expect, type Page } from '@playwright/test';
import { MockApiHelper } from '../helpers/MockApiHelper';

import projectsFixture from '../fixtures/projects.json';
import testsFixture from '../fixtures/tests.json';
import testSetsFixture from '../fixtures/test-sets.json';
import testRunsFixture from '../fixtures/test-runs.json';
import behaviorsFixture from '../fixtures/behaviors.json';
import endpointsFixture from '../fixtures/endpoints.json';
import tasksFixture from '../fixtures/tasks.json';
import tokensFixture from '../fixtures/tokens.json';
import tracesFixture from '../fixtures/traces.json';
import projectDetailFixture from '../fixtures/project-detail.json';
import knowledgeDetailFixture from '../fixtures/knowledge-detail.json';
import testDetailFixture from '../fixtures/test-detail.json';
import testSetDetailFixture from '../fixtures/test-set-detail.json';
import testRunDetailFixture from '../fixtures/test-run-detail.json';
import taskDetailFixture from '../fixtures/task-detail.json';
import endpointDetailFixture from '../fixtures/endpoint-detail.json';
import testResultsFixture from '../fixtures/test-results.json';

/**
 * Visual regression tests — each overview page is screenshotted against
 * deterministic fixture data and compared to a committed baseline.
 *
 * First run: creates the baseline snapshots (stored in tests/e2e/snapshots/).
 * Subsequent runs: fail if any page differs by more than maxDiffPixelRatio.
 * To update baselines: npx playwright test --update-snapshots --grep @visual
 *
 * Tagged @visual so they run in the dedicated "visual" playwright project
 * (Chromium, 1280×800) and can be scheduled separately from PR checks.
 */

/** Dynamic content selectors to mask before snapshotting. */
function getDynamicMasks(page: Page) {
  return [
    // Relative timestamps ("2 hours ago", "Jan 15")
    page.locator('[class*="timestamp"], [data-testid*="time"]'),
    // Avatar images (contain user-specific content)
    page.locator('[alt*="avatar"], [aria-label*="avatar"]'),
    // Any chip or badge with a numeric count that can change
    page.locator('.MuiBadge-badge'),
  ];
}

const SNAPSHOT_OPTIONS = {
  maxDiffPixelRatio: 0.02,
  threshold: 0.2,
} as const;

// ---------------------------------------------------------------------------
// Pages with fixture data (deterministic populated state)
// ---------------------------------------------------------------------------

test('Projects — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/projects', projectsFixture as any[]);
  await page.goto('/projects');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('projects.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Tests — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/tests', testsFixture as any[]);
  await page.goto('/tests');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('tests.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Sets — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/test_sets', testSetsFixture as any[]);
  await page.goto('/test-sets');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-sets.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Runs — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/test_runs', testRunsFixture as any[]);
  await page.goto('/test-runs');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-runs.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Behaviors — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/behaviors', behaviorsFixture as any[]);
  await page.goto('/behaviors');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('behaviors.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Endpoints — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/endpoints', endpointsFixture as any[]);
  await page.goto('/endpoints');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('endpoints.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Tasks — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/tasks', tasksFixture as any[]);
  await page.goto('/tasks');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('tasks.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('API Tokens — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/tokens', tokensFixture as any[]);
  await page.goto('/tokens');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('tokens.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

// ---------------------------------------------------------------------------
// Pages that need their own API mocks for stable baselines
// ---------------------------------------------------------------------------

test('Dashboard — visual baseline @visual', async ({ page }) => {
  // Dashboard fetches test-runs and test-results for KPI widgets
  const mock = new MockApiHelper(page);
  await mock.mockList('/test_runs', testRunsFixture as any[]);
  await mock.mockList('/test_results', testResultsFixture as any[]);
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('dashboard.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Playground — visual baseline @visual', async ({ page }) => {
  // Playground fetches the endpoints list for the selector dropdown
  const mock = new MockApiHelper(page);
  await mock.mockList('/endpoints', endpointsFixture as any[]);
  await page.goto('/playground');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('playground.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Results — visual baseline @visual', async ({ page }) => {
  // Test Results dashboard fetches both test-results and test-runs
  const mock = new MockApiHelper(page);
  await mock.mockList('/test_results', testResultsFixture as any[]);
  await mock.mockList('/test_runs', testRunsFixture as any[]);
  await page.goto('/test-results');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-results.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Traces — visual baseline @visual', async ({ page }) => {
  // Traces page fetches telemetry/trace entries
  const mock = new MockApiHelper(page);
  await mock.mockList('/telemetry', tracesFixture as any[]);
  await page.goto('/traces');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('traces.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Org Settings — visual baseline @visual', async ({ page }) => {
  // Org settings form loads from the session — no list endpoint to mock.
  // Mask all input values so org-specific data doesn't break the baseline.
  await page.goto('/organizations/settings');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('org-settings.png', {
    mask: [
      ...getDynamicMasks(page),
      page.locator('input[type="text"]'),
      page.locator('input[type="email"]'),
    ],
    ...SNAPSHOT_OPTIONS,
  });
});

test('Org Team — visual baseline @visual', async ({ page }) => {
  // Org team page loads members from the API — mask member rows so user-specific
  // names/emails don't break the baseline.
  await page.goto('/organizations/team');
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('org-team.png', {
    mask: [
      ...getDynamicMasks(page),
      page.locator('[role="row"]:not([aria-rowindex="1"])'),
    ],
    ...SNAPSHOT_OPTIONS,
  });
});

// ---------------------------------------------------------------------------
// Detail page visual baselines
// ---------------------------------------------------------------------------

const PROJECT_ID = 'a1b2c3d4-0001-0001-0001-000000000001';
const KNOWLEDGE_ID = 'c2d3e4f5-0009-0009-0009-000000000001';
const TEST_ID = 'b1c2d3e4-0002-0002-0002-000000000001';
const TEST_SET_ID = 'c1d2e3f4-0003-0003-0003-000000000001';
const TEST_RUN_ID = 'd1e2f3a4-0004-0004-0004-000000000001';
const TASK_ID = 'a2b3c4d5-0007-0007-0007-000000000001';
const ENDPOINT_ID = 'f1a2b3c4-0006-0006-0006-000000000001';

test('Project Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail('/projects', PROJECT_ID, projectDetailFixture as any);
  await mock.mockList('/endpoints', endpointsFixture as any[]);
  await page.goto(`/projects/${PROJECT_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('project-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Knowledge Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail(
    '/sources',
    KNOWLEDGE_ID,
    knowledgeDetailFixture as any
  );
  await page.goto(`/knowledge/${KNOWLEDGE_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('knowledge-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail('/tests', TEST_ID, testDetailFixture as any);
  await page.goto(`/tests/${TEST_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Set Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockList('/test_sets', [testSetDetailFixture as any]);
  await mock.mockList('/tests', testsFixture as any[]);
  await page.goto(`/test-sets/${TEST_SET_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-set-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Test Run Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail('/test_runs', TEST_RUN_ID, testRunDetailFixture as any);
  await mock.mockList('/test_results', testResultsFixture as any[]);
  await page.goto(`/test-runs/${TEST_RUN_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('test-run-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Task Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail('/tasks', TASK_ID, taskDetailFixture as any);
  await page.goto(`/tasks/${TASK_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('task-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});

test('Endpoint Detail — visual baseline @visual', async ({ page }) => {
  const mock = new MockApiHelper(page);
  await mock.mockDetail(
    '/endpoints',
    ENDPOINT_ID,
    endpointDetailFixture as any
  );
  await page.goto(`/endpoints/${ENDPOINT_ID}`);
  await page.waitForLoadState('networkidle');

  await expect(page).toHaveScreenshot('endpoint-detail.png', {
    mask: getDynamicMasks(page),
    ...SNAPSHOT_OPTIONS,
  });
});
