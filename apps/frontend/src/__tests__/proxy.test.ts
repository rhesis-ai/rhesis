/**
 * @jest-environment node
 *
 * Middleware (src/proxy.ts) tests.
 *
 * Runs in the node environment because NextRequest/NextResponse need the
 * fetch-API globals (Request, Headers) that jest-environment-jsdom strips.
 *
 * The auth helpers (`getFreshAccessToken`, `applyRefreshedSessionCookie`,
 * `decodeJwtUser`) and `getToken` are mocked: these tests pin down the
 * middleware's ROUTING contract — which branch runs for which session state,
 * and that every success-path response gets the refreshed cookie applied —
 * not the refresh mechanics themselves (those live in src/auth.ts).
 */
import { NextRequest, NextResponse } from 'next/server';
import { getToken } from 'next-auth/jwt';
import {
  applyRefreshedSessionCookie,
  decodeJwtUser,
  getFreshAccessToken,
} from '@/auth';
import { proxy } from '@/proxy';
import {
  DEFAULT_AUTHENTICATED_PATH,
  ONBOARDING_PATH,
} from '@/constants/paths';

jest.mock('next-auth/jwt', () => ({
  getToken: jest.fn(),
}));

jest.mock('@/auth', () => ({
  getFreshAccessToken: jest.fn(),
  applyRefreshedSessionCookie: jest.fn(),
  decodeJwtUser: jest.fn(),
}));

const mockGetToken = getToken as jest.Mock;
const mockGetFreshAccessToken = getFreshAccessToken as jest.Mock;
const mockApplyRefreshedSessionCookie = applyRefreshedSessionCookie as jest.Mock;
const mockDecodeJwtUser = decodeJwtUser as jest.Mock;

const ORIGIN = 'http://localhost:3000';
const SESSION_COOKIE_NAME = 'next-auth.session-token';

function makeRequest(pathAndQuery: string): NextRequest {
  return new NextRequest(`${ORIGIN}${pathAndQuery}`);
}

/** NextResponse.next() marks pass-through via the x-middleware-next header. */
function isPassThrough(response: NextResponse): boolean {
  return response.headers.get('x-middleware-next') === '1';
}

function redirectUrl(response: NextResponse): URL {
  const location = response.headers.get('location');
  expect(location).not.toBeNull();
  return new URL(location as string);
}

/** The session cookie is cleared when set to an empty value. */
function clearsSessionCookie(response: NextResponse): boolean {
  return response.cookies.get(SESSION_COOKIE_NAME)?.value === '';
}

/** Base64url-encoded unsigned JWT, shaped like a backend session token. */
function fakeBackendJwt(payload: Record<string, unknown>): string {
  const enc = (obj: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${enc({ alg: 'HS256', typ: 'JWT' })}.${enc(payload)}.fake-signature`;
}

const FUTURE_EXP = Math.floor(Date.now() / 1000) + 3600;

/** `organizationId: null` simulates a user who has not completed onboarding. */
function authenticatedState({
  organizationId = 'org-1',
  refreshedCookie = null,
}: {
  organizationId?: string | null;
  refreshedCookie?: string | null;
} = {}) {
  mockGetToken.mockResolvedValue({ session_token: 'stale-access-token' });
  mockGetFreshAccessToken.mockResolvedValue({
    accessToken: 'fresh-access-token',
    refreshedCookie,
  });
  mockDecodeJwtUser.mockReturnValue(
    organizationId === null ? {} : { organization_id: organizationId }
  );
}

describe('proxy middleware', () => {
  const savedEnv = {
    E2E_NO_DOCKER: process.env.E2E_NO_DOCKER,
    FRONTEND_ENV: process.env.FRONTEND_ENV,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.E2E_NO_DOCKER;
    global.fetch = jest.fn().mockResolvedValue(new Response('{}'));
  });

  afterAll(() => {
    process.env.E2E_NO_DOCKER = savedEnv.E2E_NO_DOCKER;
    process.env.FRONTEND_ENV = savedEnv.FRONTEND_ENV;
    if (savedEnv.E2E_NO_DOCKER === undefined) delete process.env.E2E_NO_DOCKER;
    if (savedEnv.FRONTEND_ENV === undefined) delete process.env.FRONTEND_ENV;
  });

  describe('public and auth paths', () => {
    it('passes through public paths without touching the session', async () => {
      const response = await proxy(makeRequest('/'));

      expect(isPassThrough(response)).toBe(true);
      expect(mockGetToken).not.toHaveBeenCalled();
      expect(mockGetFreshAccessToken).not.toHaveBeenCalled();
    });

    it('passes through /auth/signin without a session check', async () => {
      const response = await proxy(makeRequest('/auth/signin'));

      expect(isPassThrough(response)).toBe(true);
      expect(mockGetToken).not.toHaveBeenCalled();
    });

    it('clears cookies and forces return_to=/ on post-logout signin', async () => {
      const response = await proxy(
        makeRequest('/auth/signin?post_logout=true')
      );

      const url = redirectUrl(response);
      expect(url.pathname).toBe('/auth/signin');
      expect(url.searchParams.get('return_to')).toBe('/');
      expect(clearsSessionCookie(response)).toBe(true);
      // Already logged out — no backend logout call.
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('passes through /auth/signout', async () => {
      const response = await proxy(makeRequest('/auth/signout'));

      expect(isPassThrough(response)).toBe(true);
      expect(mockGetToken).not.toHaveBeenCalled();
    });
  });

  describe('unauthenticated access to protected paths', () => {
    it('redirects to home with return_to when no session cookie exists', async () => {
      mockGetToken.mockResolvedValue(null);

      const response = await proxy(makeRequest('/endpoints'));

      const url = redirectUrl(response);
      expect(url.pathname).toBe('/');
      expect(url.searchParams.get('return_to')).toBe('/endpoints');
      expect(url.searchParams.get('session_expired')).toBe('true');
      expect(mockGetFreshAccessToken).not.toHaveBeenCalled();
    });

    it('reads the session cookie under the exact NextAuth cookie name', async () => {
      mockGetToken.mockResolvedValue(null);

      await proxy(makeRequest('/endpoints'));

      expect(mockGetToken).toHaveBeenCalledWith(
        expect.objectContaining({ cookieName: SESSION_COOKIE_NAME })
      );
    });
  });

  describe('refresh failure', () => {
    it('clears the session and calls backend logout when the token cannot be refreshed', async () => {
      mockGetToken.mockResolvedValue({ session_token: 'stale-access-token' });
      mockGetFreshAccessToken.mockResolvedValue({
        accessToken: null,
        refreshedCookie: null,
      });

      const response = await proxy(makeRequest('/endpoints'));

      const url = redirectUrl(response);
      expect(url.pathname).toBe('/');
      expect(url.searchParams.get('session_expired')).toBe('true');
      expect(url.searchParams.get('force_logout')).toBe('true');
      expect(clearsSessionCookie(response)).toBe(true);

      // Backend logout is invoked with the (stale) access token so the
      // server-side session and refresh-token family get revoked too.
      expect(global.fetch).toHaveBeenCalledTimes(1);
      const logoutUrl = new URL((global.fetch as jest.Mock).mock.calls[0][0]);
      expect(logoutUrl.pathname).toBe('/auth/logout');
      expect(logoutUrl.searchParams.get('session_token')).toBe(
        'stale-access-token'
      );
    });
  });

  describe('authenticated access', () => {
    it('passes through when the user has an organization', async () => {
      authenticatedState();

      const response = await proxy(makeRequest('/endpoints'));

      expect(isPassThrough(response)).toBe(true);
      expect(mockDecodeJwtUser).toHaveBeenCalledWith('fresh-access-token');
    });

    it('redirects users without an organization to onboarding', async () => {
      authenticatedState({ organizationId: null });

      const response = await proxy(makeRequest('/endpoints'));

      expect(redirectUrl(response).pathname).toBe(ONBOARDING_PATH);
    });

    it('redirects onboarded users away from the onboarding page', async () => {
      authenticatedState();

      const response = await proxy(makeRequest(ONBOARDING_PATH));

      expect(redirectUrl(response).pathname).toBe(DEFAULT_AUTHENTICATED_PATH);
    });

    it('lets users without an organization reach the onboarding page', async () => {
      authenticatedState({ organizationId: null });

      const response = await proxy(makeRequest(ONBOARDING_PATH));

      expect(isPassThrough(response)).toBe(true);
    });
  });

  describe('refreshed-cookie persistence', () => {
    it('applies the refreshed cookie to pass-through responses', async () => {
      authenticatedState({ refreshedCookie: 'new-encoded-cookie' });

      const response = await proxy(makeRequest('/endpoints'));

      expect(mockApplyRefreshedSessionCookie).toHaveBeenCalledWith(
        response,
        'new-encoded-cookie'
      );
    });

    it('applies the refreshed cookie to onboarding redirects', async () => {
      authenticatedState({
        organizationId: null,
        refreshedCookie: 'new-encoded-cookie',
      });

      const response = await proxy(makeRequest('/endpoints'));

      expect(redirectUrl(response).pathname).toBe(ONBOARDING_PATH);
      expect(mockApplyRefreshedSessionCookie).toHaveBeenCalledWith(
        response,
        'new-encoded-cookie'
      );
    });

    it('still invokes the (no-op) apply when nothing was refreshed', async () => {
      authenticatedState({ refreshedCookie: null });

      const response = await proxy(makeRequest('/endpoints'));

      expect(mockApplyRefreshedSessionCookie).toHaveBeenCalledWith(
        response,
        null
      );
    });
  });

  describe('E2E local verification (E2E_NO_DOCKER)', () => {
    beforeEach(() => {
      process.env.E2E_NO_DOCKER = '1';
      process.env.FRONTEND_ENV = 'test';
    });

    it('clears the session when the local token fails verification', async () => {
      // Expired token — fails the local exp check.
      const expiredJwt = fakeBackendJwt({
        exp: Math.floor(Date.now() / 1000) - 60,
        user: { organization_id: 'org-1' },
      });
      mockGetToken.mockResolvedValue({ session_token: expiredJwt });

      const response = await proxy(makeRequest('/endpoints'));

      const url = redirectUrl(response);
      expect(url.searchParams.get('force_logout')).toBe('true');
      expect(clearsSessionCookie(response)).toBe(true);
      // Rejected locally — no refresh attempt against a backend that
      // doesn't exist in no-docker runs.
      expect(mockGetFreshAccessToken).not.toHaveBeenCalled();
    });

    it('proceeds through the normal flow when the local token verifies', async () => {
      const validJwt = fakeBackendJwt({
        exp: FUTURE_EXP,
        user: { organization_id: 'org-1' },
      });
      mockGetToken.mockResolvedValue({ session_token: validJwt });
      mockGetFreshAccessToken.mockResolvedValue({
        accessToken: validJwt,
        refreshedCookie: null,
      });
      mockDecodeJwtUser.mockReturnValue({ organization_id: 'org-1' });

      const response = await proxy(makeRequest('/endpoints'));

      expect(isPassThrough(response)).toBe(true);
    });
  });
});
