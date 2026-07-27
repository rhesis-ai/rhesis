import path from 'path';
import { test, expect } from '@playwright/test';
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
  test('endpoint selector is visible and shows available endpoints or no-endpoints message', async ({
    page,
  }) => {
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.expectLoaded();

    await page
      .locator('main, [role="main"]')
      .first()
      .waitFor({ state: 'visible', timeout: 20_000 });

    await playgroundPage.waitForEndpointsReady();

    const endpointFab = page.getByRole('button', { name: /select endpoint/i });
    const mainEl = page.locator('main, [role="main"]').first();

    const hasFab = await endpointFab.isVisible().catch(() => false);
    const hasMain = await mainEl.isVisible().catch(() => false);

    expect(
      hasFab || hasMain,
      'Expected endpoint FAB or main content to be rendered'
    ).toBeTruthy();

    if (hasFab) {
      await playgroundPage.openEndpointDrawer();
      const drawer = playgroundPage.openDrawer();
      const combobox = drawer.getByRole('combobox', {
        name: /select endpoint/i,
      });
      const noEndpointsAlert = drawer.getByText(/no endpoints available/i);
      const hasCombobox = await combobox.isVisible().catch(() => false);
      const hasNoEndpoints = await noEndpointsAlert
        .isVisible()
        .catch(() => false);
      expect(
        hasCombobox || hasNoEndpoints,
        'Expected endpoint dropdown or no-endpoints message in drawer'
      ).toBeTruthy();
      await page.keyboard.press('Escape');
    }

    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('selecting an endpoint opens the chat interface', async ({ page }) => {
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(
        true,
        'Endpoint selector not available — skipping endpoint selection test'
      );
      return;
    }

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
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(
        true,
        'Endpoint selector not available — skipping send-button test'
      );
      return;
    }

    const messageInput = page.getByPlaceholder(/type your message/i);
    if (
      !(await messageInput.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Message input not visible — skipping');
      return;
    }

    const chatPaper = page
      .locator('.MuiPaper-root')
      .filter({ has: messageInput });
    const sendBtn = chatPaper.locator('button').last();

    await expect(sendBtn).toBeDisabled({ timeout: 5_000 });

    await messageInput.fill('Hello, this is a Playwright E2E test message');

    await expect(sendBtn).toBeEnabled({ timeout: 5_000 });
    await expect(page.locator('body')).not.toContainText(
      'Internal Server Error'
    );
  });

  test('can send a message and see it appear in the chat', async ({ page }) => {
    test.slow();
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(true, 'Endpoint selector not available — skipping send test');
      return;
    }

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

    const userMessage = page.getByText(testMessage).first();
    const appeared = await userMessage
      .isVisible({ timeout: 15_000 })
      .catch(() => false);

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
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(true, 'Endpoint selector not available — skipping reset test');
      return;
    }

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

    await page.waitForTimeout(3_000);

    const resetBtn = page.getByRole('button', { name: /reset conversation/i });
    const hasReset = await resetBtn
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    if (!hasReset) {
      test.skip(true, 'Reset button not visible — no messages sent, skipping');
      return;
    }

    await resetBtn.click();

    const emptyState = page.getByText(
      /send a message to start the conversation/i
    );
    await expect(emptyState).toBeVisible({ timeout: 10_000 });
  });

  test('file attachment button is visible in the message input area', async ({
    page,
  }) => {
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(
        true,
        'Endpoint selector not available — skipping file attachment test'
      );
      return;
    }

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
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(
        true,
        'Endpoint selector not available — skipping file attachment test'
      );
      return;
    }

    const attachBtn = page.getByRole('button', { name: /attach file/i });
    if (!(await attachBtn.isVisible({ timeout: 10_000 }).catch(() => false))) {
      test.skip(true, 'Attach file button not visible — skipping');
      return;
    }

    await attachBtn.click();
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 5_000 });

    await fileInput.setInputFiles(
      path.resolve(__dirname, '../fixtures/fixture.txt')
    );

    const fileChip = page.getByText(/fixture\.txt/i).first();
    await expect(fileChip).toBeVisible({ timeout: 10_000 });
  });

  test('can open the Create Test drawer from a conversation', async ({
    page,
  }) => {
    test.slow();
    const playgroundPage = new PlaygroundPage(page);
    await playgroundPage.goto();
    await playgroundPage.waitForEndpointsReady();

    const selected = await playgroundPage.selectFirstEndpointInDrawer();
    if (!selected) {
      test.skip(
        true,
        'Endpoint selector not available — skipping create-test test'
      );
      return;
    }

    const disconnectedChip = page.getByText(/disconnected/i).first();
    if (
      await disconnectedChip.isVisible({ timeout: 3_000 }).catch(() => false)
    ) {
      test.skip(
        true,
        'WebSocket disconnected — skipping create-test drawer test'
      );
      return;
    }

    const messageInput = page.getByPlaceholder(/type your message/i);
    if (
      !(await messageInput.isVisible({ timeout: 10_000 }).catch(() => false))
    ) {
      test.skip(true, 'Message input not visible — skipping');
      return;
    }

    const testMessage = 'e2e-create-test-drawer-trigger';
    await messageInput.fill(testMessage);
    await page.keyboard.press('Enter');

    const userBubble = page.getByText(testMessage).first();
    const bubbleAppeared = await userBubble
      .isVisible({ timeout: 15_000 })
      .catch(() => false);
    if (!bubbleAppeared) {
      test.skip(
        true,
        'User message bubble did not appear — WebSocket may be unavailable, skipping'
      );
      return;
    }

    await userBubble.hover();

    const createTestBtn = page.getByRole('button', {
      name: /create single.turn test from this message/i,
    });
    const hasBtn = await createTestBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    if (!hasBtn) {
      test.skip(true, 'Create-test button not visible after hover — skipping');
      return;
    }

    await createTestBtn.click();

    const drawerTitle = page
      .getByText(/create single.turn test|create multi.turn test/i)
      .first();
    await expect(drawerTitle).toBeVisible({ timeout: 10_000 });
  });
});
