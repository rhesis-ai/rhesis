/**
 * @jest-environment node
 *
 * The module under test imports `next/server`, which needs the Web `Request`
 * global that the default jsdom environment does not provide.
 */
import { NextRequest } from 'next/server';
import { cacheControlFor, proxyToBackend } from '../backend-proxy';

describe('cacheControlFor', () => {
  it('lets the browser keep exchange rates for an hour', () => {
    expect(cacheControlFor('GET', '/services/exchange-rates', 200)).toBe(
      'private, max-age=3600'
    );
  });

  it.each([
    ['GET', '/services/exchange-rates', 500],
    ['POST', '/services/exchange-rates', 200],
    ['GET', '/usage', 200],
    ['GET', '/projects', 200],
  ])('keeps %s %s (%s) out of the browser cache', (method, path, status) => {
    expect(cacheControlFor(method, path, status)).toBe('no-store');
  });
});

describe('proxyToBackend Cache-Control', () => {
  const fetchMock = jest.fn();
  const originalFetch = global.fetch;

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('sends the per-path header on the response', async () => {
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
    const req = new NextRequest(
      'https://app.example.com/api/backend/services/exchange-rates'
    );

    const res = await proxyToBackend(req, {
      backendPath: '/services/exchange-rates',
    });

    expect(res.headers.get('cache-control')).toBe('private, max-age=3600');
  });
});
