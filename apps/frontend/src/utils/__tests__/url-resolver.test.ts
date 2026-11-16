import {
  resolveLocalhostUrl,
  getPublicApiUrl,
  getServerBackendUrl,
  getBaseUrl,
  getWebSocketUrl,
} from '../url-resolver';

describe('resolveLocalhostUrl', () => {
  it('replaces localhost with 127.0.0.1', () => {
    expect(resolveLocalhostUrl('http://localhost:8080')).toBe(
      'http://127.0.0.1:8080'
    );
  });

  it('replaces all occurrences of localhost', () => {
    expect(
      resolveLocalhostUrl('http://localhost:8080/api?host=localhost')
    ).toBe('http://127.0.0.1:8080/api?host=127.0.0.1');
  });

  it('does not modify URLs without localhost', () => {
    expect(resolveLocalhostUrl('http://example.com:8080')).toBe(
      'http://example.com:8080'
    );
  });

  it('handles empty string', () => {
    expect(resolveLocalhostUrl('')).toBe('');
  });
});

/** `API_BASE_URL` only fills what API users see; the browser never calls it. */
describe('getPublicApiUrl', () => {
  const originalRuntimeEnv = window.__ENV__;

  beforeEach(() => {
    window.__ENV__ = undefined;
  });

  afterAll(() => {
    window.__ENV__ = originalRuntimeEnv;
  });

  it('returns the configured URL as written, without a trailing slash', () => {
    window.__ENV__ = { apiBaseUrl: 'https://api.example.com/' };
    expect(getPublicApiUrl()).toBe('https://api.example.com');
  });

  it('keeps localhost, since people copy this into their own terminal', () => {
    window.__ENV__ = { apiBaseUrl: 'http://localhost:8080' };
    expect(getPublicApiUrl()).toBe('http://localhost:8080');
  });

  it.each([undefined, ''])('is undefined when unset (%p)', apiBaseUrl => {
    window.__ENV__ = { apiBaseUrl };
    expect(getPublicApiUrl()).toBeUndefined();
  });
});

/**
 * The browser's WebSocket stays on the frontend origin unless WS_URL points
 * elsewhere (local dev and docker-compose, where nothing routes /ws).
 */
describe('getWebSocketUrl', () => {
  const originalRuntimeEnv = window.__ENV__;
  const origin = window.location.origin;

  afterAll(() => {
    window.__ENV__ = originalRuntimeEnv;
  });

  it('defaults to /ws on this origin', () => {
    window.__ENV__ = {};
    expect(getWebSocketUrl()).toBe(`${origin.replace(/^http/, 'ws')}/ws`);
  });

  it('ignores API_BASE_URL', () => {
    window.__ENV__ = { apiBaseUrl: 'https://api.example.com' };
    expect(getWebSocketUrl()).toBe(`${origin.replace(/^http/, 'ws')}/ws`);
  });

  it('resolves a WS_URL path against this origin', () => {
    window.__ENV__ = { wsUrl: '/socket' };
    expect(getWebSocketUrl()).toBe(`${origin.replace(/^http/, 'ws')}/socket`);
  });

  it('uses a full WS_URL as given', () => {
    window.__ENV__ = { wsUrl: 'ws://localhost:8260/ws' };
    expect(getWebSocketUrl()).toBe('ws://localhost:8260/ws');
  });
});

describe('getServerBackendUrl', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('uses BACKEND_URL when set', () => {
    process.env.BACKEND_URL = 'http://localhost:8080/api';
    expect(getServerBackendUrl()).toBe('http://127.0.0.1:8080/api');
  });

  it('falls back to default when env var is not set', () => {
    delete (process.env as Record<string, string | undefined>).BACKEND_URL;
    expect(getServerBackendUrl()).toBe('http://backend:8080');
  });
});

describe('getBaseUrl', () => {
  const originalEnv = process.env;
  const originalRuntimeEnv = window.__ENV__;

  beforeEach(() => {
    process.env = { ...originalEnv };
    window.__ENV__ = undefined;
  });

  afterAll(() => {
    process.env = originalEnv;
    window.__ENV__ = originalRuntimeEnv;
  });

  it('returns the same-origin BFF proxy path when window is defined (browser)', () => {
    // window is defined in jsdom. Every browser request goes through the
    // same-origin `/api/backend` proxy, never the runtime-config apiBaseUrl.
    window.__ENV__ = {
      apiBaseUrl: 'http://localhost:5000',
    };
    expect(getBaseUrl()).toBe(`${window.location.origin}/api/backend`);
  });
});
