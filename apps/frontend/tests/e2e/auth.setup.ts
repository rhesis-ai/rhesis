import fs from 'fs';
import { test as setup, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';

/**
 * Authentication setup — runs once before all tests.
 *
 * Relies on backend Quick Start mode, which auto-logs in via the
 * /auth/local-login endpoint and redirects to /dashboard. The resulting
 * browser state (cookies, localStorage)
 * is persisted to tests/e2e/.auth/user.json so every test project that
 * depends on "setup" starts already authenticated.
 */
setup('authenticate via Quick Start', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.loginViaQuickStart();

  // Verify we landed on the dashboard
  await expect(page).toHaveURL(/\/dashboard/);

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

  // Ensure the .auth directory exists — it is gitignored so it won't be
  // present on a fresh checkout or in CI without an explicit mkdir step.
  await fs.promises.mkdir('tests/e2e/.auth', { recursive: true });

  // Persist the authenticated browser state (cookies + localStorage)
  await page.context().storageState({ path: 'tests/e2e/.auth/user.json' });
});
