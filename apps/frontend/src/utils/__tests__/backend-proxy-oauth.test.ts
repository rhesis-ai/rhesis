/**
 * @jest-environment node
 *
 * The module under test imports `next/server`, which needs the Web `Request`
 * global that the default jsdom environment does not provide.
 */
import { NextRequest } from 'next/server';
import {
  OAUTH_COOKIE_NAME,
  carriesOAuthCookie,
  isOAuthNavigation,
  proxyToBackend,
} from '../backend-proxy';

/**
 * The backend keeps OAuth/SSO handshake state in the `rhesis-oauth` cookie,
 * which now lives on the frontend origin. The proxy carries it only on the
 * login, callback and logout routes: the backend reads a `user_id` in it as a
 * login, so it must never reach any other route.
 */
describe('OAuth path rules', () => {
  it.each([
    '/auth/login/google',
    '/auth/callback',
    '/auth/sso/acme',
    '/auth/sso/callback',
  ])('treats GET %s as an OAuth navigation', path => {
    expect(isOAuthNavigation('GET', path)).toBe(true);
    expect(carriesOAuthCookie('GET', path)).toBe(true);
  });

  it.each([
    ['POST', '/auth/login/email'],
    ['POST', '/auth/register'],
    ['GET', '/auth/providers'],
    ['GET', '/projects'],
    ['POST', '/auth/callback'],
  ])('does not treat %s %s as an OAuth navigation', (method, path) => {
    expect(isOAuthNavigation(method, path)).toBe(false);
    expect(carriesOAuthCookie(method, path)).toBe(false);
  });

  it('lets logout carry the cookie so the backend can clear it', () => {
    expect(isOAuthNavigation('GET', '/auth/logout')).toBe(false);
    expect(carriesOAuthCookie('GET', '/auth/logout')).toBe(true);
  });
});

describe('proxyToBackend cookies and headers', () => {
  const fetchMock = jest.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  function upstream(status: number, headers: [string, string][]): Response {
    const h = new Headers();
    for (const [name, value] of headers) h.append(name, value);
    return new Response(null, { status, headers: h });
  }

  function sentHeaders(): Record<string, string> {
    return fetchMock.mock.calls[0][1].headers as Record<string, string>;
  }

  const browserCookies = [
    `${OAUTH_COOKIE_NAME}=state123`,
    'next-auth.session-token=secret-jwe',
    'other=1',
  ].join('; ');

  it('forwards only the OAuth cookie on a login, and returns every Set-Cookie', async () => {
    fetchMock.mockResolvedValue(
      upstream(302, [
        ['location', 'https://accounts.google.com/o/oauth2/auth?x=1'],
        [
          'set-cookie',
          `${OAUTH_COOKIE_NAME}=new; Path=/; Expires=Thu, 01 Jan 2099 00:00:00 GMT; HttpOnly`,
        ],
        ['set-cookie', 'second=2; Path=/'],
      ])
    );
    const req = new NextRequest(
      'https://app.example.com/api/backend/auth/login/google?return_to=%2Fhome',
      {
        headers: {
          cookie: browserCookies,
          referer: 'https://app.example.com/',
        },
      }
    );

    const res = await proxyToBackend(req, {
      backendPath: '/auth/login/google',
    });

    expect(sentHeaders().cookie).toBe(`${OAUTH_COOKIE_NAME}=state123`);
    expect(sentHeaders().referer).toBe('https://app.example.com/');
    expect(res.status).toBe(302);
    // The IdP redirect must reach the browser, not be followed here.
    expect(res.headers.get('location')).toContain('accounts.google.com');
    expect(res.headers.getSetCookie()).toEqual([
      `${OAUTH_COOKIE_NAME}=new; Path=/; Expires=Thu, 01 Jan 2099 00:00:00 GMT; HttpOnly`,
      'second=2; Path=/',
    ]);
  });

  it('sends no cookie and returns no Set-Cookie on an ordinary call', async () => {
    fetchMock.mockResolvedValue(
      upstream(200, [
        ['content-type', 'application/json'],
        ['set-cookie', `${OAUTH_COOKIE_NAME}=x; Path=/`],
      ])
    );
    const req = new NextRequest(
      'https://app.example.com/api/backend/auth/login/email',
      {
        method: 'POST',
        headers: { cookie: browserCookies, referer: 'https://evil.example/' },
        body: '{}',
      }
    );

    const res = await proxyToBackend(req, {
      backendPath: '/auth/login/email',
    });

    expect(sentHeaders().cookie).toBeUndefined();
    expect(sentHeaders().referer).toBeUndefined();
    expect(res.headers.getSetCookie()).toEqual([]);
  });

  it('passes the browser host on for the backend loopback and quick-start checks', async () => {
    fetchMock.mockResolvedValue(upstream(200, []));
    const req = new NextRequest('http://localhost:3180/api/backend/projects');

    await proxyToBackend(req, { backendPath: '/projects' });

    expect(sentHeaders()['x-forwarded-host']).toBe('localhost:3180');
    // The backend copies this into its scheme; its trailing-slash redirects
    // would then point off the origin the proxy follows.
    expect(sentHeaders()['x-forwarded-proto']).toBeUndefined();
  });
});
