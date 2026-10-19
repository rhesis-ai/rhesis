import {
  DEFAULT_SUPPORT_EMAIL,
  readRuntimeContentEnv,
} from '@/config/runtime-env';

describe('readRuntimeContentEnv', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    delete process.env.SUPPORT_EMAIL;
    delete process.env.TEST_SETS_EMPTY_STATE_VIDEO_URL;
    delete process.env.TEST_SETS_EMPTY_STATE_ARTICLE_URLS;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('falls back to the default support address', () => {
    process.env.SUPPORT_EMAIL = '  ';

    expect(readRuntimeContentEnv()).toEqual({
      supportEmail: DEFAULT_SUPPORT_EMAIL,
      emptyStates: {},
    });
  });

  it('reads the support address and per-entity empty states', () => {
    process.env.SUPPORT_EMAIL = 'support@example.com';
    process.env.TEST_SETS_EMPTY_STATE_VIDEO_URL = 'https://youtu.be/abc';

    expect(readRuntimeContentEnv()).toEqual({
      supportEmail: 'support@example.com',
      emptyStates: {
        'test-sets': {
          videoUrl: 'https://youtu.be/abc',
          articleUrls: undefined,
        },
      },
    });
  });
});
