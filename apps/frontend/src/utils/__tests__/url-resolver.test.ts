import {
  resolveLocalhostUrl,
  getClientApiBaseUrl,
  getServerBackendUrl,
  getBaseUrl,
  shouldUseDevApiProxy,
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

describe('shouldUseDevApiProxy', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv, NODE_ENV: 'development' };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns true when API host differs from page host in development', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'https://dev-api.rhesis.ai';
    expect(shouldUseDevApiProxy()).toBe(true);
  });

  it('returns false when API origin matches page origin', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost';
    expect(shouldUseDevApiProxy()).toBe(false);
  });

  it('returns false for loopback API on a different port', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8080';
    expect(shouldUseDevApiProxy()).toBe(false);
  });

  it('returns false outside development', () => {
    process.env.NODE_ENV = 'production';
    process.env.NEXT_PUBLIC_API_BASE_URL = 'https://dev-api.rhesis.ai';
    expect(shouldUseDevApiProxy()).toBe(false);
  });
});

describe('getClientApiBaseUrl', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv, NODE_ENV: 'development' };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('uses same-origin /api proxy when API host differs in development', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'https://dev-api.rhesis.ai';
    expect(getClientApiBaseUrl()).toBe('http://localhost/api');
  });

  it('uses NEXT_PUBLIC_API_BASE_URL when set', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:9090/api';
    expect(getClientApiBaseUrl()).toBe('http://127.0.0.1:9090/api');
  });

  it('falls back to default when env var is not set', () => {
    delete (process.env as Record<string, string | undefined>)
      .NEXT_PUBLIC_API_BASE_URL;
    expect(getClientApiBaseUrl()).toBe('http://127.0.0.1:8080');
  });

  it('resolves localhost in the URL', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:3000';
    expect(getClientApiBaseUrl()).toBe('http://127.0.0.1:3000');
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

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns client URL when window is defined (browser)', () => {
    // window is defined in jsdom
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:5000';
    expect(getBaseUrl()).toBe('http://127.0.0.1:5000');
  });
});
