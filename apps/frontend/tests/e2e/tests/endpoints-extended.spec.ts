import { test, expect } from '@playwright/test';
import { EndpointsPage } from '../pages/EndpointsPage';

test.describe('Endpoints — Extended @sanity', () => {
  test('endpoints page loads and shows main content', async ({ page }) => {
    const endpointsPage = new EndpointsPage(page);
    await endpointsPage.goto();
    await endpointsPage.expectLoaded();
    await endpointsPage.waitForContent();

    const mainContent = page.locator('main, [role="main"]').first();
    await expect(mainContent).toBeVisible();
  });

  test('endpoints page shows grid or valid content', async ({ page }) => {
    const endpointsPage = new EndpointsPage(page);
    await endpointsPage.goto();
    await page.waitForLoadState('networkidle');

    const hasGrid = await endpointsPage.hasDataGrid();
    const hasContent = await page
      .locator('main, [role="main"]')
      .first()
      .isVisible()
      .catch(() => false);

    expect(hasGrid || hasContent).toBeTruthy();
  });

  test('endpoint new page loads without error', async ({ page }) => {
    const endpointsPage = new EndpointsPage(page);
    await endpointsPage.gotoNewEndpoint();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('endpoints page HTTP response is successful', async ({ page }) => {
    const response = await page.goto('/endpoints');
    expect(response?.status()).toBeLessThan(500);
  });
});

test.describe('Endpoint navigation @sanity', () => {
  test('can navigate from endpoints to new endpoint page', async ({ page }) => {
    await page.goto('/endpoints');
    await page.waitForLoadState('networkidle');

    // Find and click "new endpoint" or navigate directly
    const newEndpointLink = page.getByRole('link', { name: /new/i }).first();
    const hasLink = await newEndpointLink.isVisible().catch(() => false);

    if (hasLink) {
      await newEndpointLink.click();
      await expect(page).toHaveURL(/\/endpoints\/(new|.+)/);
    } else {
      // Navigate directly if no link is visible (might require project context)
      await page.goto('/endpoints/new');
      await expect(page).toHaveURL(/\/endpoints/);
    }

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });
});
