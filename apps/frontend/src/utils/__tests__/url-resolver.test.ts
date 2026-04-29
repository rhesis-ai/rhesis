import {
  resolveLocalhostUrl,
  getClientApiBaseUrl,
  getClientUpstreamApiBaseUrl,
  getServerBackendUrl,
  getBaseUrl,
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

describe('getClientApiBaseUrl', () => {
  it('returns relative /api for same-origin browser requests', () => {
    expect(getClientApiBaseUrl()).toBe('/api');
  });
});

describe('getClientUpstreamApiBaseUrl', () => {
  it('returns relative /api/upstream for backend auth paths', () => {
    expect(getClientUpstreamApiBaseUrl()).toBe('/api/upstream');
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

  it('returns client proxy URL when window is defined (browser)', () => {
    expect(getBaseUrl()).toBe('/api');
  });
});
