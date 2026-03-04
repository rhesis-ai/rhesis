import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Rhesis frontend E2E tests.
 *
 * Uses Quick Start mode for authentication (NEXT_PUBLIC_QUICK_START=true)
 * to bypass OAuth and enable local-login flow during tests.
 */
export default defineConfig({
  testDir: './tests/e2e',
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

    // PR suite on Chromium: @sanity + @crud + @mocked only.
    // Excludes @visual and @performance which are run on a nightly schedule.
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      grepInvert: /@visual|@performance/,
    },

    // Smoke-only run on Firefox — keeps cross-browser coverage fast
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        storageState: 'tests/e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      grep: /@sanity/,
    },

    // API-mocked state tests — deterministic empty/populated/error scenarios
    {
      name: 'mocked',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      grep: /@mocked/,
    },

    // Visual regression — screenshot baseline comparisons (run nightly)
    {
      name: 'visual',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/e2e/.auth/user.json',
        viewport: { width: 1280, height: 800 },
      },
      dependencies: ['setup'],
      grep: /@visual/,
      snapshotPathTemplate:
        'tests/e2e/snapshots/{projectName}/{testFilePath}/{arg}{ext}',
    },

    // Performance threshold tests — LCP, TTFB, Load (run nightly)
    {
      name: 'performance',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/e2e/.auth/user.json',
      },
      dependencies: ['setup'],
      grep: /@performance/,
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
