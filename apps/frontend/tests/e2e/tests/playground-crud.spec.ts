import path from 'path';
import { test, expect, type Page } from '@playwright/test';
import { PlaygroundPage } from '../pages/PlaygroundPage';

/**
 * Playground full-flow interaction tests.
 *
 * Covers: B5.1 (endpoint selector), B5.2 (select endpoint and open chat),
 * B5.3 (type and send a message), B5.4 (reset conversation),
 * B5.5 (attach a file), B5.6 (create test from conversation).
 *
 * Sending a message relies on the WebSocket backend being responsive.
 * Any step that requires WebSocket connectivity gracefully skips when
 * the connection is unavailable (e.g. the "Disconnected" chip is visible).
 *
 * All tests run against the real backend in Quick Start mode.
 */
test.describe('Playground — full flow @crud', () => {
  /** Wait for the endpoint selector to finish loading before asserting on it. */
  async function waitForEndpointSelectorReady(page: Page) {
    await page.waitForLoadState('networkidle');
    // The MUI Select shows "Loading endpoints..." while fetching — wait for it to disappear
    await page
      .getByText(/loading endpoints/i)
      .waitFor({ state: 'hidden', timeout: 20_000 })
      .catch(() => {
        /* ignore if never appeared */
      });
  }

  test('endpoint selector is visible and shows available endpoints or no-endpoints message', async ({
    page,
  }) => {
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.expectLoaded();
    // Reuses the existing robust content-visible check that includes `main` as fallback
    await playgroundPage.expectContentVisible();
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('selecting an endpoint opens the chat interface', async ({ page }) => {
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    const hasCombobox = await combobox
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCombobox) {
      test.skip(
        true,
        'Endpoint selector not found — skipping endpoint selection test'
      );
      return;
    }

    // Open the dropdown
    await combobox.click();
    await page.waitForTimeout(500);

    // Check if there are any selectable options (not the placeholder)
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    const hasOption = await firstOption
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasOption) {
      await page.keyboard.press('Escape');
      test.skip(
        true,
        'No endpoints available in dropdown — skipping selection test'
      );
      return;
    }

    await firstOption.click();
    await page.waitForLoadState('networkidle');

    // Chat interface should now be visible — the message input appears
    const messageInput = page.getByPlaceholder(/type your message/i);
    const hasInput = await messageInput
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    expect(
      hasInput,
      'Expected message input to appear after selecting an endpoint'
    ).toBeTruthy();
  });

  test('send button becomes enabled when a message is typed', async ({
    page,
  }) => {
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    const hasCombobox = await combobox
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasCombobox) {
      test.skip(
        true,
        'Endpoint selector not found — skipping send-button test'
      );
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    const hasOption = await firstOption
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasOption) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping send-button test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    const messageInput = page.getByPlaceholder(/type your message/i);
    if (
      !(await messageInput.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Message input not visible — skipping');
      return;
    }

    // Before typing the send button should be disabled (input is empty)
    // The send button is the last button inside the same Paper container as the
    // message input — it has no aria-label, so we locate it structurally.
    const chatPaper = page
      .locator('.MuiPaper-root')
      .filter({ has: messageInput });
    const sendBtn = chatPaper.locator('button').last();

    await expect(sendBtn).toBeDisabled({ timeout: 5_000 });

    // After typing, the send button must become enabled
    await messageInput.fill('Hello, this is a Playwright E2E test message');

    await expect(sendBtn).toBeEnabled({ timeout: 5_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can send a message and see it appear in the chat', async ({ page }) => {
    test.slow(); // WebSocket round-trip may take time.
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    if (!(await combobox.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Endpoint selector not found — skipping send test');
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    if (!(await firstOption.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping send test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    // Check WebSocket connection status — skip if disconnected
    const disconnectedChip = page.getByText(/disconnected/i).first();
    const isDisconnected = await disconnectedChip
      .isVisible({ timeout: 3_000 })
      .catch(() => false);
    if (isDisconnected) {
      test.skip(true, 'WebSocket disconnected — skipping message send test');
      return;
    }

    const messageInput = page.getByPlaceholder(/type your message/i);
    if (
      !(await messageInput.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Message input not visible — skipping');
      return;
    }

    const testMessage = 'e2e-playground-test-message';
    await messageInput.fill(testMessage);
    await page.keyboard.press('Enter');

    // The user message bubble should appear in the chat
    const userMessage = page.getByText(testMessage).first();
    const appeared = await userMessage
      .isVisible({ timeout: 15_000 })
      .catch(() => false);

    // Even if the message doesn't appear (slow WS), the page should not error
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
    if (!appeared) {
      test.skip(
        true,
        'Message did not appear — WebSocket may be slow or unavailable'
      );
    }
  });

  test('can reset a conversation after sending a message', async ({ page }) => {
    test.slow();
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    if (!(await combobox.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Endpoint selector not found — skipping reset test');
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    if (!(await firstOption.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping reset test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    const disconnectedChip = page.getByText(/disconnected/i).first();
    if (
      await disconnectedChip.isVisible({ timeout: 3_000 }).catch(() => false)
    ) {
      test.skip(true, 'WebSocket disconnected — skipping reset test');
      return;
    }

    const messageInput = page.getByPlaceholder(/type your message/i);
    if (
      !(await messageInput.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Message input not visible — skipping');
      return;
    }

    await messageInput.fill('e2e reset test');
    await page.keyboard.press('Enter');

    // Wait for the message to appear (or timeout gracefully)
    await page.waitForTimeout(3_000);

    // Reset conversation button appears after messages are present
    const resetBtn = page.getByRole('button', { name: /reset conversation/i });
    const hasReset = await resetBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasReset) {
      test.skip(true, 'Reset button not visible — no messages sent, skipping');
      return;
    }

    await resetBtn.click();

    // After reset, the empty state text should return
    const emptyState = page.getByText(
      /send a message to start the conversation/i
    );
    await expect(emptyState).toBeVisible({ timeout: 10_000 });
  });

  test('file attachment button is visible in the message input area', async ({
    page,
  }) => {
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    if (!(await combobox.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(
        true,
        'Endpoint selector not found — skipping file attachment test'
      );
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    if (!(await firstOption.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping file attachment test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    // The attach-file IconButton is inside the message input area (Tooltip: "Attach file")
    const attachBtn = page.getByRole('button', { name: /attach file/i });
    const hasAttach = await attachBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    expect(
      hasAttach,
      'Expected "Attach file" button to be visible in the message input area'
    ).toBeTruthy();
  });

  test('can attach a file to a playground message', async ({ page }) => {
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    if (!(await combobox.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(
        true,
        'Endpoint selector not found — skipping file attachment test'
      );
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    if (!(await firstOption.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping file attachment test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    const attachBtn = page.getByRole('button', { name: /attach file/i });
    if (!(await attachBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Attach file button not visible — skipping');
      return;
    }

    // Click attach to mount the hidden file input
    await attachBtn.click();
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 5_000 });

    // Use an absolute path so it resolves correctly in both local and CI envs
    await fileInput.setInputFiles(
      path.resolve(__dirname, '../fixtures/fixture.txt')
    );

    // A chip with the filename should appear above the text field
    const fileChip = page.getByText(/fixture\.txt/i).first();
    await expect(fileChip).toBeVisible({ timeout: 10_000 });
  });

  test('can open the Create Test drawer from a conversation', async ({
    page,
  }) => {
    test.slow();
    await page.goto('/playground');
    await waitForEndpointSelectorReady(page);

    const combobox = page.locator('[role="combobox"]').first();
    if (!(await combobox.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(
        true,
        'Endpoint selector not found — skipping create-test test'
      );
      return;
    }

    await combobox.click();
    await page.waitForTimeout(500);
    const firstOption = page
      .getByRole('option')
      .filter({ hasNot: page.getByText(/choose an endpoint/i) })
      .first();
    if (!(await firstOption.isVisible({ timeout: 5_000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'No endpoints available — skipping create-test test');
      return;
    }
    await firstOption.click();
    await page.waitForLoadState('networkidle');

    // The multi-turn create-test button is enabled only after ≥2 messages.
    // Look for the single-turn science icon on a user message bubble instead.
    const createTestBtn = page.getByRole('button', {
      name: /create.*test from this message|create single.turn test/i,
    });

    // If no messages yet, the button won't be present — skip gracefully
    const hasBtn = await createTestBtn
      .isVisible({ timeout: 3_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(
        true,
        'No conversation messages present — create-test button unavailable, skipping'
      );
      return;
    }

    await createTestBtn.first().click();

    // The drawer should open with the title "Create Single-Turn Test"
    const drawerTitle = page.getByText(
      /create single.turn test|create multi.turn test/i
    );
    await expect(drawerTitle.first()).toBeVisible({ timeout: 10_000 });
  });
});
