'use client';

import React from 'react';
import { Box, Button, Paper, Skeleton, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { ArrowOutwardIcon } from '@/components/icons';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import type {
  EmptyStateAction,
  EmptyStateArticle,
  EmptyStateLinkCard,
  EntityEmptyStateEnrichment,
} from '@/constants/entity-empty-state-types';
import {
  getYouTubeThumbnailUrl,
  getYouTubeWatchUrl,
} from '@/utils/onboarding-video';

interface OgMetadata {
  title: string | null;
  description: string | null;
  imageUrl: string | null;
}

function useOgMetadata(url: string | undefined, enabled: boolean) {
  const [metadata, setMetadata] = React.useState<OgMetadata | null>(null);
  const [loading, setLoading] = React.useState(enabled);

  React.useEffect(() => {
    if (!enabled || !url) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetch(`/api/og-metadata?url=${encodeURIComponent(url)}`)
      .then(async response => {
        if (!response.ok) return null;
        return response.json() as Promise<OgMetadata>;
      })
      .then(data => {
        if (!cancelled) {
          setMetadata(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMetadata(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [url, enabled]);

  return { metadata, loading };
}

function EnrichmentActionButton({
  action,
  variant,
  showAddIcon = false,
  enriched = false,
}: {
  action: EmptyStateAction;
  variant: 'outlined' | 'contained';
  showAddIcon?: boolean;
  enriched?: boolean;
}) {
  const commonSx = enriched
    ? {
        fontWeight: 700,
        fontSize: 14,
        lineHeight: '22px',
        borderRadius: BORDER_RADIUS.sm,
        textTransform: 'none' as const,
        px: '16px',
        py: '8px',
        ...(variant === 'outlined'
          ? { borderWidth: 2, '&:hover': { borderWidth: 2 } }
          : {}),
      }
    : undefined;

  if (action.href) {
    return (
      <Button
        component="a"
        href={action.href}
        target="_blank"
        rel="noopener noreferrer"
        variant={variant}
        startIcon={showAddIcon ? <AddIcon /> : undefined}
        disabled={action.disabled}
        sx={commonSx}
      >
        {action.label}
      </Button>
    );
  }

  if (!action.onAction) return null;

  return (
    <Button
      variant={variant}
      startIcon={showAddIcon ? <AddIcon /> : undefined}
      onClick={action.onAction}
      disabled={action.disabled}
      sx={commonSx}
    >
      {action.label}
    </Button>
  );
}

function EmptyStateMedia({
  youtubeSource,
  alt,
}: {
  youtubeSource: string;
  alt?: string;
}) {
  const [quality, setQuality] = React.useState<'maxresdefault' | 'hqdefault'>(
    'maxresdefault'
  );
  const thumbnailUrl = getYouTubeThumbnailUrl(youtubeSource, quality);
  const watchUrl = getYouTubeWatchUrl(youtubeSource) ?? youtubeSource;

  if (!thumbnailUrl) return null;

  return (
    <Box
      component="a"
      href={watchUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={alt ?? 'Watch product demo video'}
      sx={{
        display: 'block',
        width: '100%',
        maxWidth: 734,
        borderRadius: BORDER_RADIUS.md,
        overflow: 'hidden',
        textDecoration: 'none',
      }}
    >
      <Box
        component="img"
        src={thumbnailUrl}
        alt={alt ?? 'Product demo video thumbnail'}
        onError={() => {
          if (quality === 'maxresdefault') {
            setQuality('hqdefault');
          }
        }}
        sx={{
          display: 'block',
          width: '100%',
          height: 'auto',
          borderRadius: BORDER_RADIUS.md,
        }}
      />
    </Box>
  );
}

function EmptyStateArticleCard({ article }: { article: EmptyStateArticle }) {
  const shouldFetch =
    !article.title && !article.description && !article.imageUrl;
  const { metadata, loading } = useOgMetadata(article.href, shouldFetch);

  const title = article.title ?? metadata?.title ?? article.href;
  const description = article.description ?? metadata?.description ?? '';
  const imageUrl = article.imageUrl ?? metadata?.imageUrl ?? null;

  const content = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        alignItems: 'flex-start',
        width: '100%',
      }}
    >
      {loading ? (
        <Skeleton variant="rounded" width="100%" height={148} />
      ) : (
        imageUrl && (
          <Box
            component="img"
            src={imageUrl}
            alt=""
            sx={{
              width: '100%',
              height: 148,
              objectFit: 'cover',
              borderRadius: BORDER_RADIUS.sm,
            }}
          />
        )
      )}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 14,
            lineHeight: '22px',
            color: theme => theme.palette.greyscale.title,
          }}
        >
          {loading ? <Skeleton width="80%" /> : title}
        </Typography>
        {(loading || description) && (
          <Typography
            sx={{
              fontSize: 12,
              lineHeight: '18px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            {loading ? <Skeleton width="100%" /> : description}
          </Typography>
        )}
      </Box>
    </Box>
  );

  if (article.href) {
    return (
      <Box
        component="a"
        href={article.href}
        target="_blank"
        rel="noopener noreferrer"
        sx={{
          textDecoration: 'none',
          color: 'inherit',
          width: '100%',
        }}
      >
        {content}
      </Box>
    );
  }

  return content;
}

function EmptyStateLinkCard({ card }: { card: EmptyStateLinkCard }) {
  return (
    <Paper
      elevation={0}
      sx={{
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        boxShadow: '0px 3px 5px rgba(0, 0, 0, 0.09)',
        p: '30px',
        width: '100%',
        maxWidth: 358,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
          textAlign: 'center',
        }}
      >
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 16,
            lineHeight: '24px',
            color: theme => theme.palette.greyscale.title,
          }}
        >
          {card.title}
        </Typography>
        <Typography
          sx={{
            fontSize: 14,
            lineHeight: '22px',
            color: theme => theme.palette.greyscale.body,
          }}
        >
          {card.description}
        </Typography>
        {card.href && (
          <Box
            component="a"
            href={card.href}
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '3px',
              textDecoration: 'none',
              color: 'primary.main',
            }}
          >
            <ArrowOutwardIcon sx={{ fontSize: 22 }} />
            <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
              {card.linkLabel}
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}

export function EntityEmptyStateEnrichmentSections({
  enrichment,
}: {
  enrichment: EntityEmptyStateEnrichment;
}) {
  const hasHelpArticles = (enrichment.helpArticles?.items.length ?? 0) > 0;
  const communityItems =
    enrichment.communityLinks?.items.filter(card => card.href) ?? [];

  if (!hasHelpArticles && communityItems.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '40px',
        pt: '40px',
        pb: '50px',
        width: '100%',
      }}
    >
      {hasHelpArticles && enrichment.helpArticles && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: 16,
              lineHeight: '24px',
              color: 'primary.main',
            }}
          >
            {enrichment.helpArticles.title}
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                lg: 'repeat(4, 1fr)',
              },
              gap: '26px',
            }}
          >
            {enrichment.helpArticles.items.map(article => (
              <EmptyStateArticleCard key={article.href} article={article} />
            ))}
          </Box>
        </Box>
      )}

      {communityItems.length > 0 && enrichment.communityLinks && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <Typography
            sx={{
              fontWeight: 700,
              fontSize: 16,
              lineHeight: '24px',
              color: 'primary.main',
            }}
          >
            {enrichment.communityLinks.title}
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                md: 'repeat(3, 1fr)',
              },
              gap: '14px',
            }}
          >
            {communityItems.map(card => (
              <EmptyStateLinkCard key={card.title} card={card} />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}

export function EnrichmentCardExtras({
  enrichment,
}: {
  enrichment: EntityEmptyStateEnrichment;
}) {
  const youtubeSource =
    enrichment.media?.youtubeUrl ?? enrichment.media?.youtubeVideoId;

  if (!youtubeSource) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: '100%',
        maxWidth: 734,
      }}
    >
      <EmptyStateMedia
        youtubeSource={youtubeSource}
        alt={enrichment.media?.alt}
      />
    </Box>
  );
}

export function EnrichmentPrimaryAction({
  actionLabel,
  onAction,
  actionDisabled,
  showAddIcon,
}: {
  actionLabel: string;
  onAction: () => void;
  actionDisabled?: boolean;
  showAddIcon?: boolean;
}) {
  return (
    <EnrichmentActionButton
      action={{
        label: actionLabel,
        onAction,
        disabled: actionDisabled,
      }}
      variant="contained"
      showAddIcon={showAddIcon}
      enriched
    />
  );
}

export function EntityEmptyStateCardShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Paper
      elevation={0}
      sx={{
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.md,
        boxShadow: ELEVATION.xs,
        px: '30px',
        py: '40px',
      }}
    >
      {children}
    </Paper>
  );
}
