import { test, expect, type Page } from '@playwright/test';

/**
 * A route's loading view renders the page itself in skeleton mode, so the
 * parts the user sees first must not move when the real page replaces it.
 * Each route is opened from another section (where the loading view shows),
 * with the page's response held back, and landmark positions are compared
 * between the loading view and the loaded page.
 *
 * Only landmarks present in both are compared: CI data differs from local, and
 * a list that loads empty shows its empty state instead of the grid.
 *
 * Tagged @sanity so it runs with the smoke tests; it skips itself on a dev
 * server, so run it against `next build` + `next start`.
 */

const ROUTES = [
  '/tests',
  '/test-sets',
  '/test-runs',
  '/endpoints',
  '/knowledge',
  '/experiments',
  '/annotations',
  '/jobs',
  '/reports',
  '/tasks',
  '/tokens',
  '/traces',
  '/metrics',
  '/models',
  '/projects',
  '/requirements',
  '/tools',
  '/insights',
  '/playground',
];

/** How long the page's own response is held, so the loading view is visible. */
const HOLD_MS = 2500;
/** When the loading view is measured: after its placeholders have faded in. */
const MEASURE_AT_MS = 600;
/** No prefetch response for this long means the loading view is cached. */
const PREFETCH_QUIET_MS = 800;
/** Time for the arrived page to render before it is measured. */
const SETTLE_MS = 1500;
const TOLERANCE_PX = 2;

const LANDMARKS = {
  title: 'main h1',
  tabs: '[role="tablist"]',
  gridHeader: '.MuiDataGrid-columnHeaders',
} as const;

type Positions = Partial<Record<keyof typeof LANDMARKS, number>>;

function measure(page: Page): Promise<Positions> {
  return page.evaluate(landmarks => {
    const out: Record<string, number> = {};
    for (const [name, selector] of Object.entries(landmarks)) {
      const el = document.querySelector(selector);
      if (el) out[name] = Math.round(el.getBoundingClientRect().y);
    }
    return out;
  }, LANDMARKS);
}

type NextWindow = {
  next: {
    router: { push: (href: string) => void };
  };
};

const isRouteRsc = (url: string, route: string) =>
  new URL(url).pathname === route && url.includes('_rsc=');

/** How long the dev overlay is given to mount before the server counts as a build. */
const DEV_OVERLAY_WAIT_MS = 5000;

test.describe('Loading view alignment @sanity', () => {
  test.setTimeout(90_000);

  // Next prefetches nothing on a dev server, so no loading view is cached and
  // there is nothing to compare. Runs against a production build.
  test.beforeAll(async ({ browser }, testInfo) => {
    const page = await browser.newPage({
      baseURL: testInfo.project.use.baseURL,
    });
    await page.goto('/');
    const isDevServer = await page
      .locator('nextjs-portal')
      .waitFor({ state: 'attached', timeout: DEV_OVERLAY_WAIT_MS })
      .then(() => true)
      .catch(() => false);
    await page.close();
    test.skip(
      isDevServer,
      'needs a production build: dev servers do not prefetch'
    );
  });

  for (const route of ROUTES) {
    test(`${route} loading view lines up with the page`, async ({ page }) => {
      // Next 16 fetches a route's loading view in several segment requests;
      // wait until they have stopped arriving.
      let lastPrefetchAt = 0;
      page.on('response', response => {
        const headers = response.request().headers();
        const isPrefetch =
          headers['next-router-prefetch'] ||
          headers['next-router-segment-prefetch'];
        if (isPrefetch && response.url().includes('_rsc=')) {
          lastPrefetchAt = Date.now();
        }
      });

      // The app's own prefetching must fetch the loading view, including for
      // sidebar links scrolled out of view; without it the view can't draw.
      await page.goto('/architect');
      await expect
        .poll(
          () =>
            lastPrefetchAt > 0 &&
            Date.now() - lastPrefetchAt > PREFETCH_QUIET_MS,
          { timeout: 30_000 }
        )
        .toBe(true);

      let hold = true;
      await page.route(/\?_rsc=/, async request => {
        const isPrefetch = Boolean(
          request.request().headers()['next-router-prefetch']
        );
        if (hold && !isPrefetch) {
          await new Promise(resolve => setTimeout(resolve, HOLD_MS));
        }
        await request.continue();
      });
      const pageArrived = page.waitForResponse(
        response =>
          isRouteRsc(response.url(), route) &&
          !response.request().headers()['next-router-prefetch']
      );

      await page.evaluate(
        target => (window as unknown as NextWindow).next.router.push(target),
        route
      );
      // The loading view is on screen: its placeholders have faded in.
      await expect(
        page.locator('main .MuiSkeleton-root').first()
      ).toBeVisible();
      await page.waitForTimeout(MEASURE_AT_MS);
      const loading = await measure(page);
      hold = false;

      await pageArrived;
      await page.waitForTimeout(SETTLE_MS);
      const loaded = await measure(page);

      expect(loading.title, 'the loading view shows the title').toBeDefined();
      for (const name of Object.keys(LANDMARKS) as (keyof Positions)[]) {
        const before = loading[name];
        const after = loaded[name];
        if (before === undefined || after === undefined) continue;
        expect(
          Math.abs(before - after),
          `${name} moves from y=${before} to y=${after}`
        ).toBeLessThanOrEqual(TOLERANCE_PX);
      }
    });
  }
});
