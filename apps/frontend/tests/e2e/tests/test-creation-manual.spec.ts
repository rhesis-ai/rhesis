import { test, expect, type Page } from '@playwright/test';
import { TestsPage } from '../pages/TestsPage';

/**
 * Manual test creation flow tests.
 *
 * Covers: B2.5 (fill a row), B2.6 (add another test case), B2.8 (save to test
 * set). The Tests page's "Manual test" button opens the writer directly; the
 * old two-step wizard (B2.3, B2.4) no longer exists. Category, topic and
 * requirement use the first option Quick Start seeds.
 */

async function openManualWriter(page: Page) {
  const testsPage = new TestsPage(page);
  await testsPage.goto();
  await testsPage.expectLoaded();

  await page.getByRole('button', { name: /^manual test$/i }).click();
  await page.waitForURL(/\/tests\/new-manual/, { timeout: 15_000 });
  await expect(
    page.getByRole('heading', { name: /^manual test writer$/i })
  ).toBeVisible();
}

const promptInputs = (page: Page) =>
  page.getByPlaceholder(/enter test prompt or scenario description/i);

test.describe('Tests — manual creation @crud', () => {
  test('opens the manual test writer from the Tests page', async ({ page }) => {
    await openManualWriter(page);
    await expect(promptInputs(page)).toHaveCount(1);
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('can add a second test case row', async ({ page }) => {
    await openManualWriter(page);

    await page.getByRole('button', { name: /^add test case$/i }).click();
    await expect(promptInputs(page)).toHaveCount(2);
  });

  test('can save tests into a new test set', async ({ page }) => {
    test.slow();
    await openManualWriter(page);

    const prompt = `e2e-manual-test-${Date.now()}`;
    await promptInputs(page).fill(prompt);
    const pickers = page
      .locator('table')
      .getByPlaceholder('Select or type new...');
    // Category, topic and requirement: take the first seeded option for each.
    for (let i = 0; i < 3; i++) {
      await pickers.nth(i).click();
      await page.getByRole('option').first().click();
    }

    await page.getByRole('button', { name: /^save$/i }).click();
    const testSetName = `e2e-manual-set-${Date.now()}`;
    await page
      .getByRole('textbox', { name: /test set name/i })
      .fill(testSetName);
    await page
      .getByRole('button', { name: /^save$/i })
      .last()
      .click();

    await page.waitForURL(/\/test-sets\/[^/?]+/, { timeout: 20_000 });
    await expect(page.getByText(testSetName).first()).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole('tab', { name: /^tests$/i }).click();
    await expect(page.getByText(prompt).first()).toBeVisible({
      timeout: 15_000,
    });
  });
});
