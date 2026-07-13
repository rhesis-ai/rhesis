import fs from 'fs';
import { test as setup, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { seedAuthWithoutBackend } from './helpers/seed-auth';

/**
 * Authentication setup — runs once before all tests.
 *
 * With E2E_NO_DOCKER=1 (local runs without Docker): seeds a signed-out
 * storageState JWT that proxy.ts accepts locally — no backend required.
 *
 * Otherwise relies on backend Quick Start mode, which auto-logs in via the
 * /auth/local-login endpoint and redirects to /architect. The resulting
 * browser state (cookies, localStorage)
 * is persisted to tests/e2e/.auth/user.json so every test project that
 * depends on "setup" starts already authenticated.
 */
setup('authenticate via Quick Start', async ({ page, browser }) => {
  if (process.env.E2E_NO_DOCKER === '1') {
    await seedAuthWithoutBackend(browser);
    return;
  }

  const loginPage = new LoginPage(page);
  await loginPage.loginViaQuickStart();

  // Verify we landed on the dashboard
  await expect(page).toHaveURL(/\/architect/);

  // Mark the onboarding checklist as dismissed so it never overlays test
  // interactions. The checklist is a fixed-position overlay that intercepts
  // pointer events; dismissing it here means all tests inherit a clean state.
  await page.evaluate(() => {
    try {
      const key = 'rhesis_onboarding_progress';
      const stored = localStorage.getItem(key);
      const progress = stored ? JSON.parse(stored) : {};
      localStorage.setItem(
        key,
        JSON.stringify({ ...progress, dismissed: true })
      );
    } catch (_) {
      // Non-fatal — tests will still work; the overlay may appear
    }
  });

  // Accept current T&C so TermsAcceptanceGate does not block test interactions.
  await page.evaluate(async () => {
    try {
      const res = await fetch('/api/v1/auth/accept-terms', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        // Backfill may already have run in local_init; ignore failures here.
      }
    } catch (_) {
      // Non-fatal
    }
  });

  // Ensure the .auth directory exists — it is gitignored so it won't be
  // present on a fresh checkout or in CI without an explicit mkdir step.
  await fs.promises.mkdir('tests/e2e/.auth', { recursive: true });

  // Persist the authenticated browser state (cookies + localStorage)
  await page.context().storageState({ path: 'tests/e2e/.auth/user.json' });
});
