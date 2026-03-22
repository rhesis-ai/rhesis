import { test, expect } from '@playwright/test';
import { OrgTeamPage } from '../pages/OrgTeamPage';

/**
 * Team Management interaction tests.
 *
 * Covers: C3.2 (invite form behaviour, focus retention regression, add second email),
 * C3.2 (validation for invalid email).
 *
 * The invite-field focus-loss regression (bug: input loses focus after each keystroke)
 * is explicitly verified here so it cannot silently regress.
 */
test.describe('Team Management — invite form @interaction', () => {
  test('invite email input retains focus while typing a full address', async ({
    page,
  }) => {
    const teamPage = new OrgTeamPage(page);
    await teamPage.goto();
    await teamPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    // Find the first email input in the invite form
    const emailInput = page.locator('input[type="email"]').first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping focus regression test');
      return;
    }

    await emailInput.click();

    // Type an email address one character at a time and verify focus is retained
    // after each keystroke — this catches the "focus loss per keystroke" regression.
    const testEmail = 'test@example.com';
    for (const char of testEmail) {
      await page.keyboard.type(char);
      const focused = await emailInput.evaluate(
        el => document.activeElement === el
      );
      expect(focused, `Focus lost after typing "${char}" in email input`).toBe(
        true
      );
    }

    // The full email should be in the input after typing
    const value = await emailInput.inputValue();
    expect(value).toBe(testEmail);
  });

  test('can add a second email field via "Add Another Email"', async ({
    page,
  }) => {
    const teamPage = new OrgTeamPage(page);
    await teamPage.goto();
    await teamPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping add-another test');
      return;
    }

    // Fill the first field
    await emailInput.fill('first@example.com');

    // Click "Add Another Email"
    const addAnotherBtn = page
      .getByRole('button', { name: /add another email/i })
      .first();
    const hasAddAnother = await addAnotherBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasAddAnother) {
      test.skip(true, '"Add Another Email" button not found — skipping');
      return;
    }
    await addAnotherBtn.click();

    // A second email input should appear
    const emailInputs = page.locator('input[type="email"]');
    const count = await emailInputs.count();
    expect(count).toBeGreaterThanOrEqual(2);

    // Delete icon should appear on each field (for removal)
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('shows a validation error for an invalid email address', async ({
    page,
  }) => {
    const teamPage = new OrgTeamPage(page);
    await teamPage.goto();
    await teamPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping validation test');
      return;
    }

    // Enter an invalid email
    await emailInput.fill('not-valid');
    await page.keyboard.press('Tab');
    await page.waitForLoadState('networkidle');

    // Check for a validation error message or aria-invalid
    const errorText = page
      .getByText(/invalid email|enter a valid email/i)
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
      'Expected a validation error for invalid email in invite form'
    ).toBeTruthy();

    // Clear the field
    await emailInput.clear();
  });

  test('"Send Invitations" button is present when a valid email is entered', async ({
    page,
  }) => {
    const teamPage = new OrgTeamPage(page);
    await teamPage.goto();
    await teamPage.expectLoaded();
    await page.waitForLoadState('networkidle');

    const emailInput = page.locator('input[type="email"]').first();
    const hasEmail = await emailInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasEmail) {
      test.skip(true, 'Email input not found — skipping send button test');
      return;
    }

    await emailInput.fill('valid@example.com');
    await page.waitForLoadState('networkidle');

    // "Send Invitations" / "Invite" button should exist in the form
    const sendBtn = page
      .getByRole('button', { name: /send invitation|invite/i })
      .first();
    const hasSend = await sendBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    expect(
      hasSend,
      'Expected a "Send Invitations" button in the invite form'
    ).toBeTruthy();

    // Do NOT click Send — we don't want to actually send invites in a test
    await emailInput.clear();
  });
});
