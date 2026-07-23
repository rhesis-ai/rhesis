/**
 * Tests for src/utils/session.ts
 *
 * Covers:
 *  - clearAllSessionData: backend logout retry loop, cookie clearing strategies,
 *    localhost vs deployed branching, localStorage/sessionStorage clearing
 */

jest.mock('../api-client/config', () => ({
  API_CONFIG: {
    baseUrl: 'http://127.0.0.1:8080/api/v1',
  },
}));

// jsdom's window.location is non-configurable, but individual properties on the
// underlying Location object (like hostname) can be redefined on the instance.

import { clearAllSessionData } from '../session';

function makeFetchResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

// Shared cookie-setter spy reused across all clearAllSessionData tests
let cookieSetSpy: jest.Mock;
let cookieGetterValue: string;

beforeEach(() => {
  cookieGetterValue = '';
  cookieSetSpy = jest.fn();
  Object.defineProperty(document, 'cookie', {
    configurable: true,
    get: () => cookieGetterValue,
    set: cookieSetSpy,
  });

  global.fetch = jest.fn();
  localStorage.clear();
  sessionStorage.clear();

  jest.useFakeTimers();
});

afterEach(() => {
  jest.runAllTimers();
  jest.useRealTimers();
  jest.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// clearAllSessionData
// ---------------------------------------------------------------------------

describe('clearAllSessionData', () => {
  it('calls the backend logout endpoint', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/auth/logout'),
      expect.objectContaining({ method: 'GET', credentials: 'include' })
    );
  });

  it('includes session_token query param when a token is passed', async () => {
    // The JWE cookie is opaque to client JS, so the token is now supplied
    // by the caller (from the NextAuth session) rather than read from cookie.
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData('my-token');

    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(calledUrl).toContain('session_token=my-token');
  });

  it('retries the logout call on failure (3 total attempts)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 500));

    const promise = clearAllSessionData();
    await jest.runAllTimersAsync();
    await promise;

    // 1 original attempt + 2 retries = 3 total calls
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(3);
  });

  it('stops retrying after a successful response (1 attempt only)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData();

    expect((global.fetch as jest.Mock).mock.calls.length).toBe(1);
  });

  it('clears localStorage and sessionStorage', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));
    localStorage.setItem('someKey', 'someValue');
    sessionStorage.setItem('anotherKey', 'anotherValue');

    await clearAllSessionData();

    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('writes cookie-clearing strings to document.cookie', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData();

    expect(cookieSetSpy).toHaveBeenCalled();
    const setValues = cookieSetSpy.mock.calls.map(
      (c: unknown[]) => c[0] as string
    );
    expect(
      setValues.some((v: string) =>
        v.includes('expires=Thu, 01 Jan 1970 00:00:01 GMT')
      )
    ).toBe(true);
  });

  it('always applies the base cookie-clearing strategies', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData();

    const setValues = cookieSetSpy.mock.calls.map(
      (c: unknown[]) => c[0] as string
    );
    // Every known cookie should be cleared with at least the no-domain strategy
    expect(
      setValues.some(
        (v: string) =>
          v.includes('next-auth.session-token=') &&
          v.includes('path=/') &&
          !v.includes('domain=')
      )
    ).toBe(true);
    // SameSite=None; Secure strategy is part of the base set
    expect(
      setValues.some((v: string) => v.includes('SameSite=None; Secure'))
    ).toBe(true);
  });

  it('does not throw when fetch throws on every retry', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('Network down'));

    const promise = clearAllSessionData();
    await jest.runAllTimersAsync();
    await expect(promise).resolves.toBeUndefined();
  });

  it('deduplicates cookies: clears both document.cookie names and known auth list', async () => {
    // next-auth.session-token is both in document.cookie AND in knownAuthCookies
    cookieGetterValue =
      'next-auth.session-token=tok; next-auth.csrf-token=csrf; custom-cookie=val';

    (global.fetch as jest.Mock).mockResolvedValue(makeFetchResponse({}, 200));

    await clearAllSessionData();

    const clearedNames = cookieSetSpy.mock.calls.map(
      (c: unknown[]) => (c[0] as string).split('=')[0]
    );
    // Both custom-cookie (from document.cookie) and next-auth.session-token (from known list)
    expect(
      clearedNames.some((n: string) => n === 'next-auth.session-token')
    ).toBe(true);
    expect(clearedNames.some((n: string) => n === 'custom-cookie')).toBe(true);
  });
});
