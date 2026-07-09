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
   * empty areas that do not already sit inside an elevated container.
   * Defaults to false for backward compatibility.
   *
   * Figma: Frontend node 1435:49277 (linked data / section empty state).
   */
  card?: boolean;
  /**
   * Compact section-empty visuals without an extra Paper shell. Use inside
   * `SectionCard` and other already-elevated containers to avoid double
   * borders/shadows.
   */
  embedded?: boolean;
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
 * - **Embedded** (`embedded=true`): same compact card styling without the
 *   extra Paper shell — for use inside `SectionCard`.
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
  embedded = false,
  iconSize,
  showAddIcon,
  enrichment,
}: EntityEmptyStateProps) {
  const isEnriched = hasEnrichmentContent(enrichment);
  const useCompactLayout = card || isEnriched || embedded;
  const wrapInCardShell = (card || isEnriched) && !embedded;
  const resolvedIconSize = iconSize ?? (useCompactLayout ? 32 : 64);
  const resolvedShowAddIcon = showAddIcon ?? useCompactLayout;

  const headerBlock = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: useCompactLayout ? '10px' : 0,
      }}
    >
      <Icon
        sx={{
          fontSize: resolvedIconSize,
          color: 'primary.main',
          opacity: useCompactLayout ? 1 : 0.6,
        }}
      />

      <Typography
        variant="h6"
        sx={{
          fontWeight: useCompactLayout ? 600 : 700,
          fontSize: useCompactLayout ? 20 : undefined,
          lineHeight: useCompactLayout ? '24px' : undefined,
          color: useCompactLayout ? 'primary.main' : 'text.primary',
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
        lineHeight: useCompactLayout ? '22px' : undefined,
      }}
    >
      {description}
    </Typography>
  );

  const basicAction =
    actionLabel && onAction ? (
      <Button
        variant={useCompactLayout ? 'outlined' : 'contained'}
        startIcon={resolvedShowAddIcon ? <AddIcon /> : undefined}
        onClick={onAction}
        disabled={actionDisabled}
        sx={
          useCompactLayout
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
        py: useCompactLayout ? 0 : 10,
        px: useCompactLayout ? { xs: 2, md: '200px' } : 4,
        gap: isEnriched ? '50px' : useCompactLayout ? '20px' : 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: isEnriched ? '30px' : useCompactLayout ? '20px' : 0,
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

  if (!useCompactLayout) {
    return standaloneContent;
  }

  return (
    <Box sx={{ width: '100%' }}>
      {wrapInCardShell ? (
        <EntityEmptyStateCardShell>{cardContent}</EntityEmptyStateCardShell>
      ) : (
        cardContent
      )}
      {isEnriched && enrichment && (
        <EntityEmptyStateEnrichmentSections enrichment={enrichment} />
      )}
    </Box>
  );
}
