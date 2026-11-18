/**
 * @jest-environment node
 *
 * The route imports `next/server`, which needs the Web `Request` global that
 * the default jsdom environment does not provide.
 */
import { NextRequest, NextResponse } from 'next/server';
import { GET, POST } from '../route';

const getFreshAccessToken = jest.fn();
const proxyToBackend = jest.fn();

jest.mock('@/auth', () => ({
  getFreshAccessToken: (...args: unknown[]) => getFreshAccessToken(...args),
  applyRefreshedSessionCookie: jest.fn(),
}));

jest.mock('@/utils/backend-proxy', () => ({
  ...jest.requireActual('@/utils/backend-proxy'),
  proxyToBackend: (...args: unknown[]) => proxyToBackend(...args),
}));

/**
 * The browser reaches the backend only through this route, including sign-in
 * before there is a session and OAuth/SSO navigations from other sites.
 */
describe('/api/backend BFF route', () => {
  beforeEach(() => {
    getFreshAccessToken.mockReset();
    proxyToBackend
      .mockReset()
      .mockResolvedValue(NextResponse.json({ ok: true }));
  });

  function request(
    path: string,
    init: { method?: string; site?: string } = {}
  ): NextRequest {
    const headers: Record<string, string> = {};
    if (init.site) headers['sec-fetch-site'] = init.site;
    return new NextRequest(`https://app.example.com/api/backend${path}`, {
      method: init.method ?? 'GET',
      headers,
    });
  }

  function forwarded(): { backendPath: string; overrideHeaders?: object } {
    return proxyToBackend.mock.calls[0][1];
  }

  it('forwards sign-in without a session and without Authorization', async () => {
    getFreshAccessToken.mockResolvedValue({ accessToken: null });

    await POST(
      request('/auth/login/email', { method: 'POST', site: 'same-origin' })
    );

    expect(forwarded()).toEqual({ backendPath: '/auth/login/email' });
  });

  it('still answers 401 itself for other paths without a session', async () => {
    getFreshAccessToken.mockResolvedValue({ accessToken: null });

    const res = await GET(request('/projects', { site: 'same-origin' }));

    expect(res.status).toBe(401);
    expect(res.headers.get('x-auth-origin')).toBe('bff');
    expect(proxyToBackend).not.toHaveBeenCalled();
  });

  it('injects Authorization when there is a session', async () => {
    getFreshAccessToken.mockResolvedValue({ accessToken: 'tok' });

    await GET(request('/projects', { site: 'same-origin' }));

    expect(forwarded()).toEqual({
      backendPath: '/projects',
      overrideHeaders: { authorization: 'Bearer tok' },
    });
  });

  it.each(['/auth/callback', '/auth/sso/callback', '/auth/sso/acme'])(
    'lets the cross-site navigation to %s through, with no session',
    async path => {
      getFreshAccessToken.mockResolvedValue({ accessToken: 'tok' });

      const res = await GET(request(path, { site: 'cross-site' }));

      expect(res.status).toBe(200);
      // The OAuth `state` check protects these; no token rides along.
      expect(forwarded()).toEqual({ backendPath: path });
      expect(getFreshAccessToken).not.toHaveBeenCalled();
    }
  );

  it.each([
    ['GET', '/auth/logout'],
    ['GET', '/projects'],
    ['POST', '/auth/callback'],
  ])('still rejects cross-site %s %s', async (method, path) => {
    const handler = method === 'GET' ? GET : POST;
    const res = await handler(request(path, { method, site: 'cross-site' }));

    expect(res.status).toBe(403);
    expect(proxyToBackend).not.toHaveBeenCalled();
  });
});
