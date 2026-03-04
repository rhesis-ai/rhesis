import { test, expect } from '@playwright/test';
import {
  measurePagePerf,
  measureLCP,
  PERF_THRESHOLDS,
} from '../helpers/PerformanceHelper';

/**
 * Performance threshold tests — each overview page is measured for:
 *   - TTFB (Time to First Byte)
 *   - DomContentLoaded
 *   - Load event
 *   - LCP (Largest Contentful Paint)
 *
 * Thresholds are defined in PerformanceHelper.ts and aligned with Google's
 * "needs improvement" boundaries. Failures here indicate a performance
 * regression, not a functional bug.
 *
 * Tagged @performance so they run in the dedicated "performance" playwright
 * project (Chromium only) and can be scheduled nightly rather than on every PR.
 *
 * Note: /generation redirects immediately, so its LCP will be 0 — excluded.
 */

const perfRoutes = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/projects', name: 'Projects' },
  { path: '/knowledge', name: 'Knowledge' },
  { path: '/behaviors', name: 'Behaviors' },
  { path: '/playground', name: 'Playground' },
  { path: '/tests', name: 'Tests' },
  { path: '/test-sets', name: 'Test Sets' },
  { path: '/test-results', name: 'Test Results' },
  { path: '/test-runs', name: 'Test Runs' },
  { path: '/traces', name: 'Traces' },
  { path: '/tasks', name: 'Tasks' },
  { path: '/endpoints', name: 'Endpoints' },
  { path: '/tokens', name: 'API Tokens' },
  { path: '/organizations/settings', name: 'Org Settings' },
  { path: '/organizations/team', name: 'Org Team' },
];

for (const route of perfRoutes) {
  test(`${route.name} meets performance thresholds @performance`, async ({
    page,
  }) => {
    await page.goto(route.path);
    await page.waitForLoadState('networkidle');

    const metrics = await measurePagePerf(page);
    const lcp = await measureLCP(page);

    expect(metrics.ttfb, `${route.name} TTFB`).toBeLessThan(
      PERF_THRESHOLDS.ttfb
    );
    expect(
      metrics.domContentLoaded,
      `${route.name} DomContentLoaded`
    ).toBeLessThan(PERF_THRESHOLDS.domContentLoaded);
    expect(metrics.load, `${route.name} Load`).toBeLessThan(
      PERF_THRESHOLDS.load
    );

    // LCP of 0 means no LCP candidate was observed (e.g. on redirect pages)
    if (lcp > 0) {
      expect(lcp, `${route.name} LCP`).toBeLessThan(PERF_THRESHOLDS.lcp);
    }
  });
}
