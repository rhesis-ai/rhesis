import { type Page } from '@playwright/test';

/**
 * Dismiss the global TermsAcceptanceGate modal when it is visible.
 * Non-fatal — used as a belt-and-suspenders guard in E2E navigation tests.
 */
export async function dismissTermsGateIfVisible(page: Page): Promise<void> {
  const dialog = page.getByRole('dialog', { name: /updated terms/i });
  const visible = await dialog.isVisible({ timeout: 2_000 }).catch(() => false);
  if (!visible) return;

  const checkbox = dialog.getByRole('checkbox');
  if (await checkbox.isVisible().catch(() => false)) {
    await checkbox.check();
  }

  await dialog.getByRole('button', { name: /accept and continue/i }).click();
  await dialog.waitFor({ state: 'hidden', timeout: 10_000 });
}

/**
 * Record terms acceptance via the API using the active NextAuth session token.
 */
export async function acceptTermsViaApi(page: Page): Promise<void> {
  const sessionResponse = await page.request.get('/api/auth/session');
  if (!sessionResponse.ok()) return;

  const session = (await sessionResponse.json()) as {
    session_token?: string;
  };
  const sessionToken = session.session_token;
  if (!sessionToken) return;

  await page.request.post('/api/v1/auth/accept-terms', {
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      'Content-Type': 'application/json',
    },
  });
}
