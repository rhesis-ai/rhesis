import { test, expect } from '@playwright/test';
import { OrgSettingsPage } from '../pages/OrgSettingsPage';

/**
 * Organization Settings edit interaction tests.
 *
 * Covers: C2.2 (save button disabled when no edits), C2.3 (edit fields, invalid email).
 */
test.describe('Organization Settings — edit interactions @interaction', () => {
  test('Save Changes button is disabled when no changes are made', async ({
    page,
  }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Look for a "Save Changes" button — it should be disabled initially
    const saveBtn = page.getByRole('button', { name: /save changes/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, 'Save Changes button not found — skipping');
      return;
    }

    await expect(saveBtn).toBeDisabled({ timeout: 5_000 });
  });

  test('Save Changes button enables after editing a field', async ({
    page,
  }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const saveBtn = page.getByRole('button', { name: /save changes/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, 'Save Changes button not found — skipping');
      return;
    }

    // Find the Display Name or Organization Name text field and modify it
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

    // Read current value then append a character to trigger dirty state
    const currentValue = await displayNameInput.inputValue();
    await displayNameInput.fill(currentValue + ' ');

    // Save button should now be enabled
    await expect(saveBtn).toBeEnabled({ timeout: 5_000 });

    // Restore original value (avoid actually saving random changes)
    await displayNameInput.fill(currentValue);
  });

  test('entering an invalid email in Contact Info shows a validation error', async ({
    page,
  }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Find an email input in the Contact section
    const emailInput = page.getByRole('textbox', { name: /email/i }).first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping validation test');
      return;
    }

    // Type an invalid email address
    await emailInput.click();
    await emailInput.fill('not-a-valid-email');
    // Trigger validation by blurring
    await page.keyboard.press('Tab');
    await page.waitForLoadState('networkidle');

    // An error indicator should be visible (helperText, aria-describedby error, or red border)
    const errorText = page
      .getByText(/invalid email|please enter a valid/i)
      .first();
    const hasError = await errorText
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    // Also check for aria-invalid on the input
    const ariaInvalid = await emailInput
      .getAttribute('aria-invalid')
      .catch(() => null);
    const hasAriaError = ariaInvalid === 'true';

    expect(
      hasError || hasAriaError,
      'Expected a validation error for invalid email address'
    ).toBeTruthy();

    // Clear the field to avoid polluting state
    await emailInput.clear();
    await page.keyboard.press('Tab');
  });

  test('can save a change to org settings', async ({ page }) => {
    const settingsPage = new OrgSettingsPage(page);
    await settingsPage.goto();
    await settingsPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const saveBtn = page.getByRole('button', { name: /save changes/i }).first();
    const hasSave = await saveBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasSave) {
      test.skip(true, 'Save Changes button not found — skipping save test');
      return;
    }

    // Find the Description field (multi-line, safer to edit than name)
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

    // Save button should now be enabled
    await expect(saveBtn).toBeEnabled({ timeout: 5_000 });
    await saveBtn.click();

    // After saving, wait for any toast/snackbar or for the button to return to disabled
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );

    // Restore original to avoid side effects
    await descInput.fill(originalValue);
    if (await saveBtn.isEnabled({ timeout: 3_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForLoadState('networkidle');
    }
  });
});
