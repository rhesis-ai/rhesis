import type { Page } from '@playwright/test';

export interface PagePerfMetrics {
  ttfb: number;
  domContentLoaded: number;
  load: number;
}

/**
 * Measures standard navigation timing metrics for the currently loaded page.
 * Must be called after page.goto() and page.waitForLoadState('networkidle').
 *
 * Returns null if navigation timing data is unavailable (e.g. on redirect
 * pages where the final URL differs from the navigated URL and the browser
 * has not yet committed a new navigation entry).
 */
export async function measurePagePerf(
  page: Page
): Promise<PagePerfMetrics | null> {
  return page.evaluate(() => {
    const entries = performance.getEntriesByType('navigation');
    if (entries.length === 0) {
      return null;
    }
    const nav = entries[0] as PerformanceNavigationTiming;
    return {
      ttfb: nav.responseStart - nav.startTime,
      domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
      load: nav.loadEventEnd - nav.startTime,
    };
  });
}

/**
 * Measures Largest Contentful Paint for the current page.
 * Returns 0 if LCP never fires within 5 seconds (e.g. on a redirect page).
 */
export async function measureLCP(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      new Promise<number>(resolve => {
        new PerformanceObserver(list => {
          const entries = list.getEntries();
          const last = entries[entries.length - 1] as PerformanceEntry & {
            startTime: number;
          };
          resolve(last.startTime);
        }).observe({ type: 'largest-contentful-paint', buffered: true });
        // Fallback: resolve with 0 if no LCP entry fires
        setTimeout(() => resolve(0), 5_000);
      })
  );
}

/** Recommended thresholds (ms). Aligned with Google's "needs improvement" boundaries. */
export const PERF_THRESHOLDS = {
  ttfb: 800,
  domContentLoaded: 3_000,
  load: 5_000,
  lcp: 4_000,
};
