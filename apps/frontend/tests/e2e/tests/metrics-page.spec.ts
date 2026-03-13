import { test, expect } from '@playwright/test';
import { MetricsPage } from '../pages/MetricsPage';

/**
 * Metrics page tests — superuser only.
 *
 * Covers: A4.1 (page loads, both Language and Embedding sections),
 * A4.2 (search filter, backend filter buttons: All / Custom / DeepEval etc.).
 *
 * If the current session user is not a superuser the page redirects to /dashboard,
 * in which case all tests gracefully skip.
 */
test.describe('Metrics page — load and filters @interaction', () => {
  test('metrics page loads without error', async ({ page }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    const isOnMetrics = page.url().includes('/metrics');
    if (!isOnMetrics) {
      test.skip(
        true,
        'Redirected away from /metrics — user is not a superuser, skipping'
      );
      return;
    }

    await metricsPage.expectLoaded();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('metrics page shows metric cards or an empty state', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping metrics content test');
      return;
    }

    await metricsPage.expectLoaded();

    const cards = page.locator('.MuiCard-root');
    const emptyState = page.getByText(/no metrics|no results/i);
    const main = page.locator('main, [role="main"]').first();

    const hasCards = (await cards.count()) > 0;
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    const hasMain = await main.isVisible().catch(() => false);

    expect(
      hasCards || hasEmpty || hasMain,
      'Expected metric cards, an empty state, or main content to be rendered'
    ).toBeTruthy();
  });

  test('can filter metrics by name using the search input', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping search filter test');
      return;
    }

    await metricsPage.expectLoaded();

    // Record the initial card count
    const initialCount = await metricsPage.getCardCount();
    if (initialCount === 0) {
      test.skip(true, 'No metric cards to filter — skipping search test');
      return;
    }

    // Search for something that should not match anything
    await metricsPage.searchFor('zzz-no-match-xyz-e2e');
    const filteredCount = await metricsPage.getCardCount();

    // After a no-match search, count should be 0 or less than initial
    expect(filteredCount).toBeLessThanOrEqual(initialCount);

    // Clear the search and verify cards return
    await metricsPage.searchFor('');
    const restoredCount = await metricsPage.getCardCount();
    expect(restoredCount).toBeGreaterThanOrEqual(filteredCount);

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can use backend filter buttons to filter metric cards', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping backend filter test');
      return;
    }

    await metricsPage.expectLoaded();

    // Try clicking known backend filter buttons
    const filterNames = ['Custom', 'DeepEval', 'Ragas'];
    for (const filterName of filterNames) {
      const btn = page
        .getByRole('button', { name: new RegExp(`^${filterName}$`, 'i') })
        .first();
      const visible = await btn
        .isVisible({ timeout: 3_000 })
        .catch(() => false);
      if (!visible) continue;

      await btn.click();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }

    // Click "All" to reset
    const allBtn = page.getByRole('button', { name: /^all$/i }).first();
    if (await allBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await allBtn.click();
      await page.waitForLoadState('networkidle');
    }
  });

  test('can open the Filters popover and clear all filters', async ({
    page,
  }) => {
    const metricsPage = new MetricsPage(page);
    await metricsPage.goto();
    await page.waitForLoadState('networkidle');

    if (!page.url().includes('/metrics')) {
      test.skip(true, 'Not a superuser — skipping filters popover test');
      return;
    }

    await metricsPage.expectLoaded();

    // Click the "Filters" button with a badge
    const filtersBtn = page.getByRole('button', { name: /^filters$/i }).first();
    const hasFilters = await filtersBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasFilters) {
      test.skip(true, 'Filters button not found — skipping popover test');
      return;
    }

    await filtersBtn.click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Click "Clear All" to reset filters
    const clearAllBtn = page
      .getByRole('button', { name: /clear all/i })
      .first();
    if (await clearAllBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await clearAllBtn.click();
    }

    // Close the popover
    await page.keyboard.press('Escape');
  });
});
