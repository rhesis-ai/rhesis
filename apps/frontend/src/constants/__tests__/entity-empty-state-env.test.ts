import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';

describe('entity-empty-state-env', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns undefined when env vars are unset', () => {
    delete process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_VIDEO_URL;
    delete process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_ARTICLE_URLS;

    expect(getEntityEmptyStateEnrichment('tests')).toBeUndefined();
  });

  it('builds enrichment from cloud env vars', () => {
    process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_VIDEO_URL =
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
    process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_ARTICLE_URLS =
      'https://docs.rhesis.ai/docs/tests,https://docs.rhesis.ai/docs/metrics';

    const enrichment = getEntityEmptyStateEnrichment('tests');

    expect(enrichment?.media?.youtubeUrl).toBe(
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    );
    expect(enrichment?.helpArticles?.items).toHaveLength(2);
    expect(enrichment?.secondaryAction?.href).toBe(
      'https://docs.rhesis.ai/docs/tests'
    );
    expect(enrichment?.communityLinks?.items.length).toBeGreaterThan(0);
  });
});
