import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Rhesis frontend E2E tests.
 *
 * Uses Quick Start mode for authentication (NEXT_PUBLIC_QUICK_START=true)
 * to bypass OAuth and enable local-login flow during tests.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 30_000,

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    // Auth setup project — runs first to create storageState
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
    },

    // Smoke tests using authenticated state
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_QUICK_START: 'true',
      NEXT_PUBLIC_API_BASE_URL:
        process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080',
      BACKEND_URL: process.env.BACKEND_URL || 'http://localhost:8080',
      NEXTAUTH_SECRET:
        process.env.NEXTAUTH_SECRET || 'test-secret-for-e2e-tests-only',
      NEXTAUTH_URL: process.env.NEXTAUTH_URL || 'http://localhost:3000',
    },
  },
});
