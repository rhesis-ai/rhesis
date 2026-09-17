/**
 * next/server needs the WHATWG Request/Response globals, which the default
 * jsdom environment does not provide.
 *
 * @jest-environment node
 */
import { NextRequest } from 'next/server';
import { GET } from '@/app/brand-fonts/[...path]/route';

jest.mock('@/auth', () => ({
  getFreshAccessToken: jest.fn(),
}));

jest.mock('@/utils/url-resolver', () => ({
  getServerBackendUrl: () => 'https://backend.test',
}));

import { getFreshAccessToken } from '@/auth';

const mockGetFreshAccessToken = getFreshAccessToken as jest.MockedFunction<
  typeof getFreshAccessToken
>;

const ORIGINAL_ENV = { ...process.env };

function request(path: string): NextRequest {
  return new NextRequest(`https://app.test/brand-fonts/${path}`);
}

function params(path: string) {
  return { params: Promise.resolve({ path: path.split('/') }) };
}

function fontResponse(body: string, contentType = 'font/ttf'): Response {
  return new Response(body, {
    status: 200,
    headers: { 'content-type': contentType },
  });
}

describe('GET /brand-fonts/[...path]', () => {
  let fetchMock: jest.SpyInstance;

  beforeEach(() => {
    mockGetFreshAccessToken.mockClear();
    fetchMock = jest.spyOn(global, 'fetch');
    mockGetFreshAccessToken.mockResolvedValue({
      accessToken: 'token',
    } as never);
    delete process.env.BRAND_FONT_BASE_URL;
    delete process.env.BRAND_FONT_FAMILY;
  });

  afterEach(() => {
    fetchMock.mockRestore();
    process.env = { ...ORIGINAL_ENV };
  });

  it('rejects a path that is not a font file', async () => {
    const response = await GET(
      request('../../etc/passwd'),
      params('..%2F..%2Fetc%2Fpasswd')
    );

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('serves the organisation font, passing the slug through for verification', async () => {
    fetchMock.mockResolvedValue(fontResponse('org-font-bytes'));

    const response = await GET(
      request('inria-sans-400.woff2'),
      params('inria-sans-400.woff2')
    );

    expect(response.status).toBe(200);
    await expect(response.text()).resolves.toBe('org-font-bytes');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain(
      '/organizations/settings/branding/assets/font-400?slug=inria-sans'
    );
    expect(init.headers.Authorization).toBe('Bearer token');
  });

  it('caches an organisation font privately, so one org never gets another’s', async () => {
    fetchMock.mockResolvedValue(fontResponse('org-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.headers.get('cache-control')).toContain('private');
  });

  it('caches a content-addressed org font immutably', async () => {
    // `?v=<hash>` means a replaced file is a different URL, so this entry can
    // never be the stale one.
    fetchMock.mockResolvedValue(fontResponse('org-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf?v=feedface'),
      params('inria-sans-400.ttf')
    );

    expect(response.headers.get('cache-control')).toContain('immutable');
  });

  it('revalidates an org font requested without a version', async () => {
    // An old page still open asks for the bare filename; without a short TTL
    // it would pin whatever bytes that URL returned first.
    fetchMock.mockResolvedValue(fontResponse('org-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.headers.get('cache-control')).toContain('must-revalidate');
  });

  it('falls back to BRAND_FONT_BASE_URL when the org has no such font', async () => {
    // A slug the deployment does not configure, so the org is checked first —
    // e.g. a page still open after the org's own font was removed.
    process.env.BRAND_FONT_BASE_URL = 'https://fonts.example.com';
    process.env.BRAND_FONT_FAMILY = 'Inria Sans';
    fetchMock
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockResolvedValueOnce(fontResponse('deployment-font-bytes'));

    const response = await GET(
      request('acme-grotesk-400.ttf'),
      params('acme-grotesk-400.ttf')
    );

    expect(response.status).toBe(200);
    await expect(response.text()).resolves.toBe('deployment-font-bytes');
    expect(fetchMock.mock.calls[1][0]).toBe(
      'https://fonts.example.com/acme-grotesk-400.ttf'
    );
  });

  it('marks a deployment font immutable, unlike an org one', async () => {
    process.env.BRAND_FONT_BASE_URL = 'https://fonts.example.com';
    process.env.BRAND_FONT_FAMILY = 'Inria Sans';
    fetchMock.mockResolvedValue(fontResponse('deployment-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.headers.get('cache-control')).toContain('immutable');
  });

  it('404s when neither an org font nor the env vars are configured', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 404 }));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.status).toBe(404);
  });

  it('skips the org lookup when the request is for the deployment font', async () => {
    // The @font-face rules name whichever family is in effect, so a request
    // for the deployment's own slug cannot be an org upload. Without this an
    // env-branded deployment paid a token refresh plus a backend round trip
    // per font file on every page load.
    process.env.BRAND_FONT_BASE_URL = 'https://fonts.example.com';
    process.env.BRAND_FONT_FAMILY = 'Inria Sans';
    fetchMock.mockResolvedValue(fontResponse('deployment-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.status).toBe(200);
    expect(mockGetFreshAccessToken).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('still checks the org for a family the deployment does not configure', async () => {
    process.env.BRAND_FONT_BASE_URL = 'https://fonts.example.com';
    process.env.BRAND_FONT_FAMILY = 'Inria Sans';
    fetchMock.mockResolvedValue(fontResponse('org-font-bytes'));

    const response = await GET(
      request('acme-grotesk-400.ttf'),
      params('acme-grotesk-400.ttf')
    );

    expect(response.status).toBe(200);
    await expect(response.text()).resolves.toBe('org-font-bytes');
  });

  it('skips the org lookup entirely for a signed-out visitor', async () => {
    mockGetFreshAccessToken.mockResolvedValue({ accessToken: null } as never);
    process.env.BRAND_FONT_BASE_URL = 'https://fonts.example.com';
    process.env.BRAND_FONT_FAMILY = 'Inria Sans';
    fetchMock.mockResolvedValue(fontResponse('deployment-font-bytes'));

    const response = await GET(
      request('inria-sans-400.ttf'),
      params('inria-sans-400.ttf')
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://fonts.example.com/inria-sans-400.ttf'
    );
  });
});
