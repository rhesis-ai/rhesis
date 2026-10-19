import {
  DEFAULT_SUPPORT_EMAIL,
  publicEnv,
  readPublicEnv,
  serverEnv,
} from '@/config/runtime-config';

describe('config/runtime-config', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = {
      ...originalEnv,
      API_BASE_URL: 'https://api.example.com',
      NEXTAUTH_SECRET: 'secret',
    };
    for (const name of [
      'SUPPORT_EMAIL',
      'BACKEND_URL',
      'FRONTEND_URL',
      'ONBOARDING_VIDEO_URL',
      'ARCHITECT_HELP_ARTICLE_URLS',
      'TEST_SETS_EMPTY_STATE_VIDEO_URL',
      'TEST_SETS_EMPTY_STATE_ARTICLE_URLS',
    ]) {
      delete process.env[name];
    }
  });

  afterEach(() => {
    delete window.__ENV__;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe('readPublicEnv', () => {
    it('falls back to defaults when nothing is set', () => {
      process.env.SUPPORT_EMAIL = '  ';

      expect(readPublicEnv()).toMatchObject({
        supportEmail: DEFAULT_SUPPORT_EMAIL,
        architectHelpArticleUrls: [],
        emptyStates: {},
      });
    });

    it('reads per-entity empty states', () => {
      process.env.TEST_SETS_EMPTY_STATE_VIDEO_URL = 'https://youtu.be/abc';
      process.env.TEST_SETS_EMPTY_STATE_ARTICLE_URLS =
        ' https://docs.rhesis.ai/a , https://docs.rhesis.ai/b ';

      expect(readPublicEnv().emptyStates).toEqual({
        'test-sets': {
          videoUrl: 'https://youtu.be/abc',
          articleUrls: ['https://docs.rhesis.ai/a', 'https://docs.rhesis.ai/b'],
        },
      });
    });

    it('caps architect help articles at four and drops disallowed hosts', () => {
      process.env.ARCHITECT_HELP_ARTICLE_URLS = [
        'https://evil.example/docs',
        'not-a-url',
        ...[1, 2, 3, 4, 5].map(n => `https://docs.rhesis.ai/docs/page-${n}`),
      ].join(',');

      expect(readPublicEnv().architectHelpArticleUrls).toEqual(
        [1, 2, 3, 4].map(n => `https://docs.rhesis.ai/docs/page-${n}`)
      );
    });

    it('never includes server-only values', () => {
      process.env.BACKEND_URL = 'http://backend:8080';
      process.env.ONBOARDING_VIDEO_URL = 'https://youtu.be/abc';

      const serialized = JSON.stringify(readPublicEnv());
      expect(serialized).not.toContain('backend:8080');
      expect(serialized).not.toContain('youtu.be/abc');
      expect(serialized).not.toContain('secret');
    });
  });

  it('serverEnv defaults the backend URL', () => {
    expect(serverEnv().backendUrl).toBe('http://backend:8080');
  });

  it('publicEnv fills gaps in a partial window.__ENV__', () => {
    window.__ENV__ = { apiBaseUrl: 'https://api.example.com' };

    expect(publicEnv()).toEqual({
      apiBaseUrl: 'https://api.example.com',
      supportEmail: DEFAULT_SUPPORT_EMAIL,
      architectHelpArticleUrls: [],
      emptyStates: {},
    });
  });
});
