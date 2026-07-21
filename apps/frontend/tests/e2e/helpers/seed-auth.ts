import fs from 'fs';
import type { Browser } from '@playwright/test';
import { encode } from 'next-auth/jwt';
import projectsFixture from '../fixtures/projects.json';
import e2eUserFixture from '../fixtures/e2e-user.json';

const AUTH_DIR = 'tests/e2e/.auth';
export const AUTH_STORAGE_PATH = `${AUTH_DIR}/user.json`;

/** Stable test user used across no-docker E2E runs. */
const E2E_USER = e2eUserFixture;

// Must match `authConfig.cookies.sessionToken.name` in src/auth.ts — the
// cookie name doubles as the JWE salt, so an encode under any other name
// produces a cookie the app cannot decrypt.
const SESSION_COOKIE_NAME = 'next-auth.session-token';

// Must match the webServer env in playwright.config.ts: this helper runs in
// the Playwright process, which does NOT inherit webServerEnv, but the JWE we
// seed here has to decrypt inside the dev server Playwright starts.
const NEXTAUTH_SECRET =
  process.env.NEXTAUTH_SECRET || 'test-secret-for-e2e-tests-only';

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

/**
 * Build a fake backend-style session JWT for proxy.ts local verification
 * (E2E_NO_DOCKER). Its signature is never verified in test mode — only the
 * payload's `exp` and `user.organization_id` are checked locally.
 */
function createFakeBackendJwt(nowSeconds: number): string {
  const payload = {
    sub: E2E_USER.id,
    iat: nowSeconds,
    exp: nowSeconds + ONE_YEAR_SECONDS,
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

/**
 * Encode the session cookie exactly the way NextAuth does in production: a
 * JWE (encrypted with NEXTAUTH_SECRET, salted by the cookie name) whose
 * payload carries the backend JWT as `session_token`. A plain unsigned JWT
 * here is useless — `getToken()`/`auth()` decrypt the cookie before reading
 * it, so proxy.ts and /api/auth/session would both treat it as "no session".
 * `access_token_expires` is a year out so the middleware never attempts a
 * refresh (there is no backend to refresh against in no-docker runs).
 */
async function createE2ESessionCookie(): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const sessionToken = createFakeBackendJwt(now);

  return encode({
    token: {
      sub: E2E_USER.id,
      user: {
        id: E2E_USER.id,
        email: E2E_USER.email,
        name: E2E_USER.name,
        image: null,
        picture: null,
        organization_id: E2E_USER.organization_id,
        is_email_verified: true,
      },
      session_token: sessionToken,
      access_token_expires: now + ONE_YEAR_SECONDS,
    },
    secret: NEXTAUTH_SECRET,
    salt: SESSION_COOKIE_NAME,
    maxAge: ONE_YEAR_SECONDS,
  });
}

/** Playwright storageState object for an authenticated Quick Start user. */
export async function buildE2EStorageState(origin = 'http://localhost:3100') {
  const sessionCookie = await createE2ESessionCookie();
  const expires = Math.floor(Date.now() / 1000) + ONE_YEAR_SECONDS;

  return {
    cookies: [
      {
        name: SESSION_COOKIE_NAME,
        value: sessionCookie,
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

  const origin = process.env.FRONTEND_URL || 'http://localhost:3100';
  const storageState = await buildE2EStorageState(origin);
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
