import { checkEnv, enforceEnv } from '@/config/enforce-env';

const CONTENT_VARS = [
  'SUPPORT_EMAIL',
  'ONBOARDING_VIDEO_URL',
  'ARCHITECT_HELP_ARTICLE_URLS',
  'TESTS_EMPTY_STATE_VIDEO_URL',
  'TESTS_EMPTY_STATE_ARTICLE_URLS',
];

describe('enforce-env', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = {
      ...originalEnv,
      API_BASE_URL: 'https://api.example.com',
      BACKEND_URL: 'http://backend:8080',
      FRONTEND_URL: 'https://app.example.com',
    };
    for (const name of CONTENT_VARS) delete process.env[name];
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe('checkEnv', () => {
    it('passes a valid environment', () => {
      process.env.ONBOARDING_VIDEO_URL = 'https://youtu.be/lLLj6S5T1Ig';
      process.env.ARCHITECT_HELP_ARTICLE_URLS =
        'https://docs.rhesis.ai/docs/endpoints';
      process.env.SUPPORT_EMAIL = 'support@example.com';

      expect(checkEnv()).toEqual({ errors: [], warnings: [] });
    });

    it('reports a missing or malformed core URL as an error', () => {
      delete process.env.API_BASE_URL;
      process.env.BACKEND_URL = 'backend:8080';

      expect(checkEnv().errors).toEqual([
        'API_BASE_URL is required but not set',
        'BACKEND_URL is not an http(s) URL: "backend:8080"',
      ]);
    });

    it('reports content the UI would not show as warnings only', () => {
      process.env.ONBOARDING_VIDEO_URL = 'https://cdn.example.com/v.mp4';
      process.env.ARCHITECT_HELP_ARTICLE_URLS = 'https://docs.example.com/x';
      process.env.TESTS_EMPTY_STATE_VIDEO_URL = 'https://vimeo.com/123';
      process.env.TESTS_EMPTY_STATE_ARTICLE_URLS =
        'https://docs.rhesis.ai/a,docs.rhesis.ai/b';
      process.env.SUPPORT_EMAIL = 'support';

      const { errors, warnings } = checkEnv();

      expect(errors).toEqual([]);
      expect(warnings).toEqual([
        'ONBOARDING_VIDEO_URL is not a YouTube or Vimeo link, so no video shows: "https://cdn.example.com/v.mp4"',
        'TESTS_EMPTY_STATE_VIDEO_URL is not a YouTube link, so no video shows: "https://vimeo.com/123"',
        'TESTS_EMPTY_STATE_ARTICLE_URLS entry is not a docs.rhesis.ai page, so it is dropped: "docs.rhesis.ai/b"',
        'ARCHITECT_HELP_ARTICLE_URLS entry is not a docs.rhesis.ai page, so it is dropped: "https://docs.example.com/x"',
        'SUPPORT_EMAIL is not an email address: "support"',
      ]);
    });
  });

  describe('enforceEnv', () => {
    function run(nodeEnv: string) {
      (process.env as Record<string, string>).NODE_ENV = nodeEnv;
      const exit = jest
        .spyOn(process, 'exit')
        .mockImplementation((() => undefined) as never);
      jest.spyOn(console, 'error').mockImplementation(() => {});
      jest.spyOn(console, 'warn').mockImplementation(() => {});
      enforceEnv();
      return exit;
    }

    it('exits in production on an error', () => {
      delete process.env.API_BASE_URL;
      expect(run('production')).toHaveBeenCalledWith(1);
    });

    it('only logs outside production', () => {
      delete process.env.API_BASE_URL;
      expect(run('development')).not.toHaveBeenCalled();
    });

    it('never exits on a warning', () => {
      process.env.SUPPORT_EMAIL = 'support';
      expect(run('production')).not.toHaveBeenCalled();
    });
  });
});
