import type {
  EntityEmptyStateEnrichment,
  EntityEmptyStateKey,
  EmptyStateLinkCard,
} from '@/constants/entity-empty-state-types';
import { getYouTubeWatchUrl } from '@/utils/onboarding-video';

const ENV_PREFIX: Record<EntityEmptyStateKey, string> = {
  projects: 'PROJECTS',
  tests: 'TESTS',
  'test-sets': 'TEST_SETS',
  'test-runs': 'TEST_RUNS',
  endpoints: 'ENDPOINTS',
  behaviors: 'BEHAVIORS',
  metrics: 'METRICS',
  experiments: 'EXPERIMENTS',
};

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

function parseCommaSeparatedUrls(value: string | undefined): string[] {
  if (!value?.trim()) return [];
  return value
    .split(',')
    .map(url => url.trim())
    .filter(Boolean)
    .slice(0, 4);
}

function readEnv(
  key: EntityEmptyStateKey,
  suffix: 'VIDEO_URL' | 'ARTICLE_URLS'
) {
  const prefix = ENV_PREFIX[key];
  return process.env[`NEXT_PUBLIC_${prefix}_EMPTY_STATE_${suffix}`]?.trim();
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
  const videoUrl = readEnv(key, 'VIDEO_URL');
  const articleUrls = parseCommaSeparatedUrls(readEnv(key, 'ARTICLE_URLS'));

  if (!videoUrl && articleUrls.length === 0) {
    return undefined;
  }

  return buildEnrichment({ videoUrl, articleUrls });
}
