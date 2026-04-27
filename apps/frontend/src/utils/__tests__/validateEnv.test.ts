import { validateEnv } from '../validateEnv';

type MutableEnv = Record<string, string | undefined>;

describe('validateEnv', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('does not throw when all required env vars are present', () => {
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).not.toThrow();
  });

  it('does not require NEXT_PUBLIC_API_BASE_URL', () => {
    delete (process.env as MutableEnv).NEXT_PUBLIC_API_BASE_URL;
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).not.toThrow();
  });

  it('throws when AUTH_SECRET is missing', () => {
    delete (process.env as MutableEnv).AUTH_SECRET;
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('AUTH_SECRET');
  });

  it('throws when GOOGLE_CLIENT_ID is missing', () => {
    process.env.AUTH_SECRET = 'secret';
    delete (process.env as MutableEnv).GOOGLE_CLIENT_ID;
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('GOOGLE_CLIENT_ID');
  });

  it('throws when GOOGLE_CLIENT_SECRET is missing', () => {
    process.env.AUTH_SECRET = 'secret';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    delete (process.env as MutableEnv).GOOGLE_CLIENT_SECRET;

    expect(() => validateEnv()).toThrow('GOOGLE_CLIENT_SECRET');
  });

  it('treats empty string as missing for AUTH_SECRET', () => {
    process.env.AUTH_SECRET = '';
    process.env.GOOGLE_CLIENT_ID = 'client-id';
    process.env.GOOGLE_CLIENT_SECRET = 'client-secret';

    expect(() => validateEnv()).toThrow('AUTH_SECRET');
  });
});
