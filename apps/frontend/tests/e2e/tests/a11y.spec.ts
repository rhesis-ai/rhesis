import AxeBuilder from '@axe-core/playwright';
import { test, expect, type Page } from '@playwright/test';

/**
 * Runs axe on every top-level route in light and dark mode and fails on any
 * serious or critical violation whose rule isn't in KNOWN_VIOLATIONS.
 *
 * The allowlist is global rather than per route because the CI backend and
 * the local mock backend serve different data, so the same page can show
 * different issues. Remove a rule here once it is fixed everywhere; never add
 * one to make a new violation pass.
 */

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

const BLOCKING_IMPACTS = new Set(['serious', 'critical']);

// color-contrast stays until the default palette is AA; the opt-in
// accessible-colours mode already clears it.
const KNOWN_VIOLATIONS = new Set<string>(['color-contrast']);

const PROTECTED_ROUTES = [
  '/dashboard',
  '/architect',
  '/requirements',
  '/metrics',
  '/knowledge',
  '/tests',
  '/test-sets',
  '/generation',
  '/playground',
  '/explorer',
  '/test-runs',
  '/test-results',
  '/insights',
  '/experiments',
  '/traces',
  '/annotations',
  '/tasks',
  '/projects',
  '/endpoints',
  '/models',
  '/tools',
  '/jobs',
  '/organizations/settings',
  '/settings',
  '/tokens',
];

const PUBLIC_ROUTES = [
  '/auth/signin',
  '/auth/register',
  '/auth/forgot-password',
];

async function expectNoNewViolations(page: Page, route: string) {
  const response = await page.goto(route);
  expect(response?.status()).toBeLessThan(500);
  // Polling and websockets can keep the network busy, so networkidle is only a
  // best effort; the visible <main> is the real readiness signal.
  await page
    .waitForLoadState('networkidle', { timeout: 15_000 })
    .catch(() => undefined);
  await expect(page.locator('main').first()).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(WCAG_TAGS)
    // Next.js dev overlay is not part of the app.
    .exclude('nextjs-portal')
    .analyze();

  await test.info().attach('axe-results', {
    body: JSON.stringify(results.violations, null, 2),
    contentType: 'application/json',
  });

  const unexpected = results.violations
    .filter(v => BLOCKING_IMPACTS.has(v.impact ?? ''))
    .filter(v => !KNOWN_VIOLATIONS.has(v.id))
    .map(v => `${v.id} (${v.impact}, ${v.nodes.length}x): ${v.help}`);

  expect(unexpected, `New accessibility violations on ${route}`).toEqual([]);
}

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`Accessibility (${colorScheme}) @a11y`, () => {
    test.use({ colorScheme });

    for (const route of PROTECTED_ROUTES) {
      test(`${route} has no new violations`, async ({ page }) => {
        await expectNoNewViolations(page, route);
      });
    }

    test.describe('signed out', () => {
      test.use({ storageState: { cookies: [], origins: [] } });

      for (const route of PUBLIC_ROUTES) {
        test(`${route} has no new violations`, async ({ page }) => {
          await expectNoNewViolations(page, route);
        });
      }
    });
  });
}
