'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import AddIcon from '@mui/icons-material/Add';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import type { EntityEmptyStateEnrichment } from '@/constants/entity-empty-state-types';
import { hasEnrichmentContent } from '@/constants/entity-empty-state-env';
import {
  EnrichmentCardExtras,
  EnrichmentPrimaryAction,
  EntityEmptyStateCardShell,
  EntityEmptyStateEnrichmentSections,
} from '@/components/common/EntityEmptyStateEnrichmentParts';

export type { EntityEmptyStateEnrichment } from '@/constants/entity-empty-state-types';

export interface EntityEmptyStateProps {
  /** SvgIcon component class (not an element). */
  icon: React.ComponentType<SvgIconProps>;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  /**
   * When true renders a Figma-aligned Paper card around the empty state
   * (white bg, border, shadow). Used for linked-entity tabs and section
   * cards on detail pages.
   * Defaults to false for backward compatibility.
   *
   * Figma: Frontend node 1435:49277 (linked data / section empty state).
   */
  card?: boolean;
  /**
   * Icon size in px. Defaults to 64 (standalone) or 32 (card variant).
   * Pass an explicit value to override.
   */
  iconSize?: number;
  /**
   * When true, shows a leading + icon on the action button. Defaults to true
   * when `card` is true.
   */
  showAddIcon?: boolean;
  /** Cloud-only enrichment (video, help articles, community). Unset = basic. */
  enrichment?: EntityEmptyStateEnrichment;
}

/**
 * Figma-aligned empty state used when an entity list is empty.
 *
 * - **Default** (`card=false`): large icon, centered text, optional CTA button.
 * - **Card** (`card=true`): bordered Paper card for section / linked-entity tabs
 *   (Figma node 1435:49277).
 * - **Enriched** (cloud env vars): v2 layout with media and help sections
 *   (Figma node 1858:51148).
 */
export default function EntityEmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionDisabled = false,
  card = false,
  iconSize,
  showAddIcon,
  enrichment,
}: EntityEmptyStateProps) {
  const isEnriched = hasEnrichmentContent(enrichment);
  const useCardShell = card || isEnriched;
  const resolvedIconSize = iconSize ?? (useCardShell ? 32 : 64);
  const resolvedShowAddIcon = showAddIcon ?? useCardShell;

  const headerBlock = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: useCardShell ? '10px' : 0,
      }}
    >
      <Icon
        sx={{
          fontSize: resolvedIconSize,
          color: 'primary.main',
          opacity: useCardShell ? 1 : 0.6,
        }}
      />

      <Typography
        variant="h6"
        sx={{
          fontWeight: useCardShell ? 600 : 700,
          fontSize: useCardShell ? 20 : undefined,
          lineHeight: useCardShell ? '24px' : undefined,
          color: useCardShell ? 'primary.main' : 'text.primary',
        }}
      >
        {title}
      </Typography>
    </Box>
  );

  const descriptionBlock = description && (
    <Typography
      variant="body2"
      sx={{
        color: 'text.secondary',
        maxWidth: isEnriched ? 734 : 480,
        lineHeight: useCardShell ? '22px' : undefined,
      }}
    >
      {description}
    </Typography>
  );

  const basicAction =
    actionLabel && onAction ? (
      <Button
        variant={useCardShell ? 'outlined' : 'contained'}
        startIcon={resolvedShowAddIcon ? <AddIcon /> : undefined}
        onClick={onAction}
        disabled={actionDisabled}
        sx={
          useCardShell
            ? {
                fontWeight: 700,
                fontSize: 18,
                lineHeight: '25px',
                borderRadius: BORDER_RADIUS.md,
                textTransform: 'none',
                px: '20px',
                py: '12px',
                borderWidth: 2,
                '&:hover': {
                  borderWidth: 2,
                },
              }
            : {
                mt: 1,
                fontWeight: 700,
                fontSize: 18,
                lineHeight: '25px',
                borderRadius: BORDER_RADIUS.pill,
                textTransform: 'none',
                px: '20px',
                py: '12px',
                boxShadow: ELEVATION.xs,
              }
        }
      >
        {actionLabel}
      </Button>
    ) : null;

  const enrichedActions =
    isEnriched && enrichment ? (
      <Box
        sx={{
          display: 'flex',
          gap: '10px',
          alignItems: 'center',
          justifyContent: 'center',
          flexWrap: 'wrap',
        }}
      >
        {enrichment.secondaryAction && (
          <Button
            component={enrichment.secondaryAction.href ? 'a' : 'button'}
            href={enrichment.secondaryAction.href}
            target={enrichment.secondaryAction.href ? '_blank' : undefined}
            rel={
              enrichment.secondaryAction.href
                ? 'noopener noreferrer'
                : undefined
            }
            variant="outlined"
            disabled={enrichment.secondaryAction.disabled}
            onClick={enrichment.secondaryAction.onAction}
            sx={{
              fontWeight: 700,
              fontSize: 14,
              lineHeight: '22px',
              borderRadius: BORDER_RADIUS.sm,
              textTransform: 'none',
              px: '16px',
              py: '8px',
              borderWidth: 2,
              '&:hover': { borderWidth: 2 },
            }}
          >
            {enrichment.secondaryAction.label}
          </Button>
        )}
        {actionLabel && onAction && (
          <EnrichmentPrimaryAction
            actionLabel={actionLabel}
            onAction={onAction}
            actionDisabled={actionDisabled}
            showAddIcon={resolvedShowAddIcon}
          />
        )}
      </Box>
    ) : null;

  const cardContent = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        py: useCardShell ? 0 : 10,
        px: useCardShell ? { xs: 2, md: '200px' } : 4,
        gap: isEnriched ? '50px' : useCardShell ? '20px' : 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: isEnriched ? '30px' : useCardShell ? '20px' : 0,
          width: isEnriched ? '100%' : undefined,
          maxWidth: isEnriched ? 734 : undefined,
        }}
      >
        {headerBlock}
        {descriptionBlock}
        {isEnriched ? enrichedActions : basicAction}
      </Box>

      {isEnriched && enrichment && (
        <EnrichmentCardExtras enrichment={enrichment} />
      )}
    </Box>
  );

  const standaloneContent = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        py: 10,
        px: 4,
        gap: 2,
      }}
    >
      {headerBlock}
      {descriptionBlock}
      {basicAction}
    </Box>
  );

  if (!useCardShell) {
    return standaloneContent;
  }

  return (
    <Box sx={{ width: '100%' }}>
      <EntityEmptyStateCardShell>{cardContent}</EntityEmptyStateCardShell>
      {isEnriched && enrichment && (
        <EntityEmptyStateEnrichmentSections enrichment={enrichment} />
      )}
    </Box>
  );
}
