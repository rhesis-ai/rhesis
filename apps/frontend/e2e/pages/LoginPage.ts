import { type Page, expect } from '@playwright/test';

/**
 * Page Object for the landing/login page.
 *
 * In Quick Start mode the app auto-logs in and redirects to /dashboard,
 * so the primary action here is simply navigating to "/" and waiting
 * for the redirect to complete.
 */
export class LoginPage {
  constructor(private readonly page: Page) {}

  /** Navigate to the landing page. */
  async goto() {
    await this.page.goto('/');
  }

  /**
   * Wait for the Quick Start auto-login to complete.
   * The app POSTs to /auth/local-login, signs in via NextAuth,
   * and redirects to /dashboard.
   */
  async waitForQuickStartLogin(timeoutMs = 30_000) {
    await this.page.waitForURL('**/dashboard', { timeout: timeoutMs });
  }

  /** Perform the full Quick Start login flow. */
  async loginViaQuickStart() {
    await this.goto();
    await this.waitForQuickStartLogin();
    await expect(this.page).toHaveURL(/\/dashboard/);
  }
}
