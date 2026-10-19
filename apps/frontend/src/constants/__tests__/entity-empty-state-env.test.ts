import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';

describe('entity-empty-state-env', () => {
  afterEach(() => {
    delete window.__ENV__;
  });

  it('returns undefined when the deployment sets nothing', () => {
    window.__ENV__ = {
      apiBaseUrl: '',
      content: { supportEmail: 'hello@rhesis.ai', emptyStates: {} },
    };

    expect(getEntityEmptyStateEnrichment('tests')).toBeUndefined();
  });

  it('builds enrichment from the runtime env', () => {
    window.__ENV__ = {
      apiBaseUrl: '',
      content: {
        supportEmail: 'hello@rhesis.ai',
        emptyStates: {
          tests: {
            videoUrl: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            articleUrls:
              'https://docs.rhesis.ai/docs/tests,https://docs.rhesis.ai/docs/metrics',
          },
        },
      },
    };

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
