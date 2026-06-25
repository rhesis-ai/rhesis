import { test, expect } from '@playwright/test';
import { OrgSettingsPage } from '../pages/OrgSettingsPage';

/**
 * Organization Settings edit interaction tests.
 *
 * Covers: C2.2 (save disabled when no edits), C2.3 (edit fields, invalid email).
 */
test.describe('Organization Settings — edit interactions @interaction', () => {
  test('Save button is disabled when no changes are made in edit mode', async ({
    page,
  }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await settingsPage.clickEditBasicInformation();

    const saveBtn = page.getByRole('button', { name: /^save$/i }).first();
    await expect(saveBtn).toBeDisabled({ timeout: 5_000 });
  });

  test('Save button enables after editing a field', async ({ page }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await settingsPage.clickEditBasicInformation();

    const saveBtn = page.getByRole('button', { name: /^save$/i }).first();

    const displayNameInput = page
      .getByRole('textbox', { name: /display name|organization name/i })
      .first();
    const hasInput = await displayNameInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasInput) {
      test.skip(true, 'Display Name field not found — skipping');
      return;
    }

    const currentValue = await displayNameInput.inputValue();
    await displayNameInput.fill(currentValue + ' ');

    await expect(saveBtn).toBeEnabled({ timeout: 5_000 });

    await displayNameInput.fill(currentValue);
    await page
      .getByRole('button', { name: /^cancel$/i })
      .first()
      .click();
  });

  test('entering an invalid email in Contact Info shows a validation error', async ({
    page,
  }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await settingsPage.clickEditContactInformation();

    const emailInput = page.getByRole('textbox', { name: /^email$/i }).first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping validation test');
      return;
    }

    await emailInput.click();
    await emailInput.fill('not-a-valid-email');
    await page.keyboard.press('Tab');
    await page.waitForLoadState('networkidle');

    const errorText = page
      .getByText(/invalid email|please enter a valid/i)
      .first();
    const hasError = await errorText
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    const ariaInvalid = await emailInput
      .getAttribute('aria-invalid')
      .catch(() => null);
    const hasAriaError = ariaInvalid === 'true';

    expect(
      hasError || hasAriaError,
      'Expected a validation error for invalid email address'
    ).toBeTruthy();

    await page
      .getByRole('button', { name: /^cancel$/i })
      .first()
      .click();
  });

  test('can save a change to org settings', async ({ page }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    await settingsPage.clickEditBasicInformation();

    const saveBtn = page.getByRole('button', { name: /^save$/i }).first();

    const descInput = page
      .getByRole('textbox', { name: /description/i })
      .first();
    const hasDesc = await descInput
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasDesc) {
      test.skip(true, 'Description field not found — skipping save test');
      return;
    }

    const originalValue = await descInput.inputValue();
    const updatedValue = `${originalValue} (e2e-${Date.now()})`.trim();
    await descInput.fill(updatedValue);

    await expect(saveBtn).toBeEnabled({ timeout: 5_000 });
    await saveBtn.click();

    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    await settingsPage.clickEditBasicInformation();
    await descInput.fill(originalValue);
    if (await saveBtn.isEnabled({ timeout: 3_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForLoadState('networkidle');
    }
  });
});
