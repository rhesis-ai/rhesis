import fs from 'fs';
import type { Browser } from '@playwright/test';
import projectsFixture from '../fixtures/projects.json';
import e2eUserFixture from '../fixtures/e2e-user.json';

const AUTH_DIR = 'tests/e2e/.auth';
export const AUTH_STORAGE_PATH = `${AUTH_DIR}/user.json`;

/** Stable test user used across no-docker E2E runs. */
const E2E_USER = e2eUserFixture;

/**
 * Build a session JWT payload compatible with NextAuth decode and proxy.ts
 * local verification (E2E_NO_DOCKER). Signature is not verified in test mode.
 */
function createE2ESessionToken(): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    sub: E2E_USER.id,
    iat: now,
    exp: now + 60 * 60 * 24 * 365,
    type: 'session',
    user: {
      id: E2E_USER.id,
      email: E2E_USER.email,
      name: E2E_USER.name,
      picture: null,
      is_superuser: false,
      is_email_verified: true,
      organization_id: E2E_USER.organization_id,
    },
  };

  const header = Buffer.from(
    JSON.stringify({ alg: 'HS256', typ: 'JWT' })
  ).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');

  return `${header}.${body}.e2e-local-no-docker`;
}

/** Playwright storageState object for an authenticated Quick Start user. */
export function buildE2EStorageState(origin = 'http://localhost:3100') {
  const sessionToken = createE2ESessionToken();
  const expires = Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 365;

  return {
    cookies: [
      {
        name: 'authjs.session-token',
        value: sessionToken,
        domain: 'localhost',
        path: '/',
        expires,
        httpOnly: true,
        secure: false,
        sameSite: 'Lax' as const,
      },
      {
        name: 'next-auth.session-token',
        value: sessionToken,
        domain: 'localhost',
        path: '/',
        expires,
        httpOnly: true,
        secure: false,
        sameSite: 'Lax' as const,
      },
      {
        name: 'rh_active_project_id',
        value: String(projectsFixture[0]?.id ?? ''),
        domain: 'localhost',
        path: '/',
        expires,
        httpOnly: false,
        secure: false,
        sameSite: 'Lax' as const,
      },
    ],
    origins: [
      {
        origin,
        localStorage: [
          {
            name: 'rhesis_onboarding_progress',
            value: JSON.stringify({
              projectCreated: false,
              endpointSetup: false,
              usersInvited: false,
              testCasesCreated: false,
              dismissed: true,
              lastUpdated: Date.now(),
            }),
          },
        ],
      },
    ],
  };
}

/**
 * Seed auth storage for Playwright runs without a live backend (E2E_NO_DOCKER).
 * Writes tests/e2e/.auth/user.json and verifies a protected route loads.
 */
export async function seedAuthWithoutBackend(browser: Browser) {
  await fs.promises.mkdir(AUTH_DIR, { recursive: true });

  const origin = process.env.NEXTAUTH_URL || 'http://localhost:3100';
  const storageState = buildE2EStorageState(origin);
  await fs.promises.writeFile(
    AUTH_STORAGE_PATH,
    JSON.stringify(storageState, null, 2)
  );

  const context = await browser.newContext({
    baseURL: origin,
    storageState: AUTH_STORAGE_PATH,
  });
  const page = await context.newPage();

  // Layout prerequisites — must not mock all /projects** as [] or /projects/mine
  // is caught and ActiveProjectContext clears rh_active_project_id.
  await page.route('**/projects/mine**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'x-total-count': String(projectsFixture.length),
        'access-control-expose-headers': 'x-total-count',
      },
      body: JSON.stringify(projectsFixture),
    })
  );

  await page.route('**/users/settings**', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ui: { theme: 'light' },
        models: {},
        notifications: {},
        default_project: { project_id: projectsFixture[0]?.id ?? null },
      }),
    })
  );

  await page.goto(`${origin}/insights`);
  await page.waitForURL(`${origin}/insights`, { timeout: 30_000 });

  await context.storageState({ path: AUTH_STORAGE_PATH });
  await context.close();
}
