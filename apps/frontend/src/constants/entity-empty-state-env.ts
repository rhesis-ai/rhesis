import type {
  EntityEmptyStateEnrichment,
  EntityEmptyStateKey,
  EmptyStateLinkCard,
} from '@/constants/entity-empty-state-types';
import { publicEnv } from '@/config/runtime-config';
import { getYouTubeWatchUrl } from '@/utils/onboarding-video';

export const COMMUNITY_LINK_CARDS: EmptyStateLinkCard[] = [
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

/** Returns enrichment when the deployment sets this entity's empty-state env vars. */
export function getEntityEmptyStateEnrichment(
  key: EntityEmptyStateKey
): EntityEmptyStateEnrichment | undefined {
  const { videoUrl, articleUrls = [] } = publicEnv().emptyStates[key] ?? {};

  if (!videoUrl && articleUrls.length === 0) {
    return undefined;
  }

  return buildEnrichment({ videoUrl, articleUrls });
}
