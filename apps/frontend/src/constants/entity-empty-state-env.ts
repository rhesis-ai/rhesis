import type {
  EntityEmptyStateEnrichment,
  EntityEmptyStateKey,
  EmptyStateLinkCard,
} from '@/constants/entity-empty-state-types';
import { getYouTubeWatchUrl } from '@/utils/onboarding-video';

const COMMUNITY_LINK_CARDS: EmptyStateLinkCard[] = [
  {
    title: 'Documentation',
    description: 'Comprehensive guides and API references',
    linkLabel: 'Browse docs',
    href: 'https://docs.rhesis.ai',
  },
  {
    title: 'Community',
    description: 'Ask questions and share feedback with other users',
    linkLabel: 'GitHub Discussions',
    href: 'https://github.com/rhesis-ai/rhesis/discussions',
  },
  {
    title: 'Issues',
    description: 'Report bugs and request features',
    linkLabel: 'GitHub Issues',
    href: 'https://github.com/rhesis-ai/rhesis/issues',
  },
];

/**
 * Static process.env access per entity so Next.js inlines NEXT_PUBLIC_* at build time.
 * Dynamic/bracket access is not replaced in client bundles.
 */
function readEntityEnvSources(key: EntityEmptyStateKey): {
  videoUrl?: string;
  articleUrls?: string;
} {
  switch (key) {
    case 'projects':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_PROJECTS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_PROJECTS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'tests':
      return {
        videoUrl: process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_TESTS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'test-sets':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_TEST_SETS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_TEST_SETS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'test-runs':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_TEST_RUNS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_TEST_RUNS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'endpoints':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_ENDPOINTS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_ENDPOINTS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'behaviors':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_BEHAVIORS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_BEHAVIORS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'metrics':
      return {
        videoUrl: process.env.NEXT_PUBLIC_METRICS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_METRICS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    case 'experiments':
      return {
        videoUrl:
          process.env.NEXT_PUBLIC_EXPERIMENTS_EMPTY_STATE_VIDEO_URL?.trim(),
        articleUrls:
          process.env.NEXT_PUBLIC_EXPERIMENTS_EMPTY_STATE_ARTICLE_URLS?.trim(),
      };
    default: {
      const _exhaustive: never = key;
      return _exhaustive;
    }
  }
}

function parseCommaSeparatedUrls(value: string | undefined): string[] {
  if (!value?.trim()) return [];
  return value
    .split(',')
    .map(url => url.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function buildEnrichment({
  videoUrl,
  articleUrls,
}: {
  videoUrl?: string;
  articleUrls: string[];
}): EntityEmptyStateEnrichment {
  const enrichment: EntityEmptyStateEnrichment = {
    communityLinks: {
      title: 'Community & Support',
      items: COMMUNITY_LINK_CARDS,
    },
  };

  if (videoUrl) {
    enrichment.media = {
      youtubeUrl: videoUrl,
      alt: 'Product demo video',
    };
  }

  if (articleUrls.length > 0) {
    enrichment.helpArticles = {
      title: 'Top Help Articles',
      items: articleUrls.map(href => ({ href })),
    };
    enrichment.secondaryAction = {
      label: 'Learn more',
      href: articleUrls[0],
    };
  } else if (videoUrl) {
    enrichment.secondaryAction = {
      label: 'Learn more',
      href: getYouTubeWatchUrl(videoUrl) ?? videoUrl,
    };
  }

  return enrichment;
}

export function hasEnrichmentContent(
  enrichment: EntityEmptyStateEnrichment | undefined
): boolean {
  if (!enrichment) return false;
  return Boolean(
    enrichment.media?.youtubeUrl ||
    enrichment.media?.youtubeVideoId ||
    (enrichment.helpArticles?.items.length ?? 0) > 0 ||
    enrichment.secondaryAction?.href ||
    enrichment.secondaryAction?.onAction
  );
}

/** Cloud-only: returns enrichment when NEXT_PUBLIC_* env vars are set. */
export function getEntityEmptyStateEnrichment(
  key: EntityEmptyStateKey
): EntityEmptyStateEnrichment | undefined {
  const { videoUrl, articleUrls: articleUrlsRaw } = readEntityEnvSources(key);
  const articleUrls = parseCommaSeparatedUrls(articleUrlsRaw);

  if (!videoUrl && articleUrls.length === 0) {
    return undefined;
  }

  return buildEnrichment({ videoUrl, articleUrls });
}
