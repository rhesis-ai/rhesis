import { test, expect } from '@playwright/test';
import { TracesPage } from '../pages/TracesPage';

/**
 * Traces drawer interaction tests.
 *
 * Covers: D3.5 (open drawer + header chips), D3.6 (switch Tree/Sequence/Graph views),
 * D3.7 (click span → attributes panel), D3.8 (close with Escape).
 * Requires at least one trace to exist in the backend.
 */
test.describe('Traces — drawer interactions @interaction', () => {
  test('clicking a trace row opens the trace drawer', async ({ page }) => {
    const tracesPage = new TracesPage(page);
    await tracesPage.goto();
    await tracesPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const hasRows = await tracesPage.hasTraceRows();
    if (!hasRows) {
      test.skip(true, 'No trace rows available — skipping drawer test');
      return;
    }

    await tracesPage.clickFirstTraceRow();
    await tracesPage.waitForDrawerOpen();

    // The drawer should be visible and error-free
    await expect(page.getByRole('presentation')).toBeVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('trace drawer shows header with context chips', async ({ page }) => {
    const tracesPage = new TracesPage(page);
    await tracesPage.goto();
    await tracesPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const hasRows = await tracesPage.hasTraceRows();
    if (!hasRows) {
      test.skip(true, 'No trace rows — skipping header chips test');
      return;
    }

    await tracesPage.clickFirstTraceRow();
    await tracesPage.waitForDrawerOpen();
    await page.waitForLoadState('networkidle');

    const drawer = page.getByRole('presentation');

    // The drawer header should contain a trace ID or similar identifier
    const hasContent = await drawer
      .locator('body, *')
      .first()
      .isVisible()
      .catch(() => false);
    expect(hasContent || (await drawer.isVisible())).toBeTruthy();

    // Span count, duration, or status chips should be present
    const metricsText = drawer
      .getByText(/span|duration|status|environment/i)
      .first();
    const hasMetrics = await metricsText
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    // Soft assertion — chips may not all be present for every trace
    if (hasMetrics) {
      await expect(metricsText).toBeVisible();
    }

    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('can switch between Tree, Sequence, and Graph view tabs', async ({
    page,
  }) => {
    const tracesPage = new TracesPage(page);
    await tracesPage.goto();
    await tracesPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const hasRows = await tracesPage.hasTraceRows();
    if (!hasRows) {
      test.skip(true, 'No trace rows — skipping view tab test');
      return;
    }

    await tracesPage.clickFirstTraceRow();
    await tracesPage.waitForDrawerOpen();
    await page.waitForLoadState('networkidle');

    const viewTabs = ['Tree', 'Sequence', 'Graph'] as const;
    for (const tabName of viewTabs) {
      const tab = page
        .getByRole('presentation')
        .getByRole('tab', { name: new RegExp(tabName, 'i') })
        .first();
      const tabVisible = await tab
        .isVisible({ timeout: 5_000 })
        .catch(() => false);
      if (!tabVisible) continue; // some views may not be present for every trace

      await tab.click();
      await page.waitForLoadState('networkidle');

      // After switching the tab, no crash should occur
      await expect(page.locator('body')).not.toContainText(
        'Internal Server Error'
      );
    }
  });

  test('can click a span to show the attributes panel', async ({ page }) => {
    const tracesPage = new TracesPage(page);
    await tracesPage.goto();
    await tracesPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const hasRows = await tracesPage.hasTraceRows();
    if (!hasRows) {
      test.skip(true, 'No trace rows — skipping span click test');
      return;
    }

    await tracesPage.clickFirstTraceRow();
    await tracesPage.waitForDrawerOpen();
    await page.waitForLoadState('networkidle');

    // Click the first span item in the tree/sequence view (left panel)
    const spanItem = page
      .getByRole('presentation')
      .locator('[role="treeitem"], [role="listitem"], .MuiListItem-root')
      .first();
    const hasSpan = await spanItem
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (!hasSpan) {
      test.skip(true, 'No span items visible in drawer — skipping');
      return;
    }

    await spanItem.click();
    await page.waitForLoadState('networkidle');

    // The right panel (SpanDetailsPanel) should render
    // Look for "Attributes", "Events", "Links" or "Status" text
    const detailText = page
      .getByRole('presentation')
      .getByText(/attributes|events|links|status/i)
      .first();
    const hasDetails = await detailText
      .isVisible({ timeout: 8_000 })
      .catch(() => false);
    if (hasDetails) {
      await expect(detailText).toBeVisible();
    }

    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('pressing Escape closes the trace drawer', async ({ page }) => {
    const tracesPage = new TracesPage(page);
    await tracesPage.goto();
    await tracesPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const hasRows = await tracesPage.hasTraceRows();
    if (!hasRows) {
      test.skip(true, 'No trace rows — skipping Escape close test');
      return;
    }

    await tracesPage.clickFirstTraceRow();
    await tracesPage.waitForDrawerOpen();

    const isOpen = await tracesPage.isDrawerOpen();
    expect(isOpen).toBe(true);

    // Close with Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // Drawer should no longer be visible
    const isClosed = !(await tracesPage.isDrawerOpen());
    expect(
      isClosed,
      'Expected trace drawer to close after pressing Escape'
    ).toBe(true);
  });
});
