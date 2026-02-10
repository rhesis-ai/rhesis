import { validateEnv } from '../validateEnv';

describe('validateEnv', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('does not throw when all required env vars are present', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8080';
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).not.toThrow();
  });

  it('throws when NEXT_PUBLIC_API_BASE_URL is missing', () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('NEXT_PUBLIC_API_BASE_URL');
  });

  it('throws when AUTH_SECRET is missing', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8080';
    delete process.env.AUTH_SECRET;
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('AUTH_SECRET');
  });

  it('throws when GOOGLE_CLIENT_ID is missing', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8080';
    process.env.AUTH_SECRET = 'secret';
    delete process.env.GOOGLE_CLIENT_ID;
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('GOOGLE_CLIENT_ID');
  });

  it('throws when GOOGLE_CLIENT_SECRET is missing', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = 'http://localhost:8080';
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    delete process.env.GOOGLE_CLIENT_SECRET;

    expect(() => validateEnv()).toThrow('GOOGLE_CLIENT_SECRET');
  });

  it('treats empty string as missing', () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = '';
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('NEXT_PUBLIC_API_BASE_URL');
  });
});
