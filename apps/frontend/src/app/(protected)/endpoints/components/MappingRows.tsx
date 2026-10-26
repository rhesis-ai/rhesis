'use client';

import React from 'react';
import { Box, Link, Tooltip, Typography } from '@mui/material';
import {
  ArrowForwardIcon,
  CheckCircleIcon,
  ErrorIcon,
  InfoIcon,
} from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';
import { SectionCard } from '@/components/common/SectionCard';
import { EmptyStateArticleCard } from '@/components/common/EntityEmptyStateEnrichmentParts';
import { publicEnv } from '@/config/runtime-config';

/** SectionCard renders subtitles as body text; these cards use the smaller grey caption. */
export function CardSubtitle({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'block',
        typography: 'caption',
        color: 'greyscale.subtitle',
      }}
    >
      {children}
    </Box>
  );
}

/**
 * SectionCard with the action beside the title only, so the description below
 * keeps the full card width instead of wrapping beside the button.
 */
export function MappingCard({
  title,
  subtitle,
  action,
  complete = false,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  /** Green border: this part has passed its check. */
  complete?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <SectionCard variant={complete ? 'success' : 'default'}>
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            // Button height, so titles line up across cards with and without one.
            minHeight: theme => theme.spacing(4.5),
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }} color="primary">
            {title}
          </Typography>
          {action}
        </Box>
        {/* Two caption lines reserved, so rows start level in side-by-side cards. */}
        {subtitle && (
          <Box
            sx={{
              mt: 1.5,
              minHeight: theme =>
                `calc(2 * ${theme.typography.caption.lineHeight})`,
            }}
          >
            {subtitle}
          </Box>
        )}
      </Box>
      {children}
    </SectionCard>
  );
}

// The theme's containedPrimary rule unsets disabled colours and outranks a plain `&.Mui-disabled`.
export const disabledContainedSx = {
  '&.MuiButton-contained.Mui-disabled': {
    bgcolor: 'action.disabledBackground',
    color: 'text.disabled',
  },
  // Same for outlined: the theme's outlinedPrimary colours make a disabled button look live.
  '&.MuiButton-outlined.Mui-disabled': {
    color: 'text.disabled',
    borderColor: 'action.disabledBackground',
  },
};

const ROW_GRID = {
  display: 'grid',
  gridTemplateColumns: '1fr auto 1fr',
  alignItems: 'center',
  columnGap: 1.5,
};

export function MappingColumnHeaders({
  left,
  right,
}: {
  left: string;
  right: string;
}) {
  return (
    <Box sx={{ ...ROW_GRID, mb: 1.5 }}>
      <Typography variant="caption" sx={{ fontWeight: 600 }} color="primary">
        {left}
      </Typography>
      <Box />
      <Typography variant="caption" sx={{ fontWeight: 600 }} color="primary">
        {right}
      </Typography>
    </Box>
  );
}

/** Grey label cell → arrow → whatever control the row maps to. */
export function MappingRow({
  label,
  info,
  children,
}: {
  label: React.ReactNode;
  info?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    // Top-aligned at the inputs' 40px height, so a helper text or a growing
    // multi-line value doesn't push the label and arrow off its first line.
    <Box sx={{ ...ROW_GRID, alignItems: 'start' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1,
          minHeight: theme => theme.spacing(5),
          px: 1.5,
          borderRadius: BORDER_RADIUS.xs,
          bgcolor: theme => theme.palette.greyscale.fieldSurface,
          minWidth: 0,
        }}
      >
        <Typography
          variant="body2"
          sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}
        >
          {label}
        </Typography>
        {info && (
          <Tooltip title={info} placement="top">
            <InfoIcon
              fontSize="small"
              sx={{
                color: 'greyscale.title',
                cursor: 'help',
                '&:hover': { color: 'primary.main' },
              }}
            />
          </Tooltip>
        )}
      </Box>
      <ArrowForwardIcon
        fontSize="small"
        sx={{ color: 'greyscale.border', mt: 1.25 }}
      />
      <Box sx={{ minWidth: 0 }}>{children}</Box>
    </Box>
  );
}

export function MappingRowList({ children }: { children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {children}
    </Box>
  );
}

export function ModeLink({
  onClick,
  disabled,
  disabledReason,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  disabledReason?: string;
  children: React.ReactNode;
}) {
  return (
    <Tooltip title={disabled ? (disabledReason ?? '') : ''}>
      <Box component="span" sx={{ alignSelf: 'flex-start' }}>
        <Link
          component="button"
          type="button"
          variant="body1"
          disabled={disabled}
          onClick={onClick}
          sx={disabled ? { color: 'text.disabled', cursor: 'default' } : {}}
        >
          {children}
        </Link>
      </Box>
    </Tooltip>
  );
}

export function TestStatusBox({
  status,
  title,
  detail,
}: {
  status: 'success' | 'error';
  title: string;
  detail?: string;
}) {
  const color = status === 'success' ? 'success.main' : 'error.main';
  // Failure messages often open with the same "HTTP 401 error from endpoint" as the title.
  const body = detail?.startsWith(title)
    ? detail.slice(title.length).replace(/^[\s:.-]+/, '')
    : detail;
  const Icon = status === 'success' ? CheckCircleIcon : ErrorIcon;
  return (
    <Box
      role={status === 'error' ? 'alert' : 'status'}
      sx={{
        border: 1,
        borderColor: color,
        borderRadius: BORDER_RADIUS.xs,
        px: 3,
        py: 2,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color }}>
        <Icon fontSize="small" />
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
      </Box>
      {body && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1, wordBreak: 'break-word' }}
        >
          {body}
        </Typography>
      )}
    </Box>
  );
}

/** Request and Response cards side by side, always the same height. */
export function TwoCardRow({
  left,
  right,
}: {
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
        gap: 3,
        alignItems: 'stretch',
        '& > * > .MuiPaper-root': {
          height: '100%',
          mb: 0,
          boxSizing: 'border-box',
        },
      }}
    >
      <Box>{left}</Box>
      <Box>{right}</Box>
    </Box>
  );
}

/** The getting-started articles the Architect shows; hidden when none are configured. */
export function HelpArticlesPanel() {
  const articleUrls = publicEnv().architectHelpArticleUrls.slice(0, 4);
  if (articleUrls.length === 0) return null;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }} color="primary">
        Help Articles
      </Typography>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            lg: 'repeat(4, 1fr)',
          },
          gap: 2.5,
        }}
      >
        {articleUrls.map(href => (
          <EmptyStateArticleCard key={href} article={{ href }} />
        ))}
      </Box>
    </Box>
  );
}
