import {
  resolveLocalhostUrl,
  getClientApiBaseUrl,
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
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('uses NEXT_PUBLIC_API_BASE_URL when set', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:9090/api';
    expect(getClientApiBaseUrl()).toBe('http://127.0.0.1:9090/api');
  });

  it('falls back to default when env var is not set', () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
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
    delete process.env.BACKEND_URL;
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
