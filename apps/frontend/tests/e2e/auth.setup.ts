import { test as setup, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';

/**
 * Authentication setup — runs once before all tests.
 *
 * Relies on Quick Start mode (NEXT_PUBLIC_QUICK_START=true) which
 * auto-logs in via the /auth/local-login endpoint and redirects
 * to /dashboard. The resulting browser state (cookies, localStorage)
 * is persisted to e2e/.auth/user.json so every test project that
 * depends on "setup" starts already authenticated.
 */
setup('authenticate via Quick Start', async ({ page }) => {
  const loginPage = new LoginPage(page);
  await loginPage.loginViaQuickStart();

  // Verify we landed on the dashboard
  await expect(page).toHaveURL(/\/dashboard/);

  // Persist the authenticated browser state
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
