'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import AddIcon from '@mui/icons-material/Add';
import type { EntityEmptyStateEnrichment } from '@/constants/entity-empty-state-types';
import { hasEnrichmentContent } from '@/constants/entity-empty-state-env';
import {
  EMPTY_STATE,
  emptyStateActionsRowSx,
  emptyStateCompactContentSx,
  emptyStateCompactTitleSx,
  emptyStateDescriptionSx,
  emptyStateEnrichedActionSx,
  emptyStateHeaderStackSx,
  emptyStateIconSx,
  emptyStateInnerStackSx,
  emptyStateOutlinedActionSx,
  emptyStateStandaloneContainedActionSx,
  emptyStateStandaloneContentSx,
  emptyStateStandaloneTitleSx,
} from '@/components/common/entityEmptyStateSx';
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
  const resolvedIconSize =
    iconSize ??
    (useCompactLayout
      ? EMPTY_STATE.iconSize.compact
      : EMPTY_STATE.iconSize.standalone);
  const resolvedShowAddIcon = showAddIcon ?? useCompactLayout;

  const headerBlock = (
    <Box sx={emptyStateHeaderStackSx(useCompactLayout)}>
      <Icon
        sx={emptyStateIconSx(resolvedIconSize, {
          standalone: !useCompactLayout,
        })}
      />

      <Typography
        variant="h6"
        sx={
          useCompactLayout
            ? emptyStateCompactTitleSx
            : emptyStateStandaloneTitleSx
        }
      >
        {title}
      </Typography>
    </Box>
  );

  const descriptionBlock = description && (
    <Typography
      variant="body2"
      sx={emptyStateDescriptionSx({
        compact: useCompactLayout,
        enriched: isEnriched,
      })}
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
            ? emptyStateOutlinedActionSx
            : emptyStateStandaloneContainedActionSx
        }
      >
        {actionLabel}
      </Button>
    ) : null;

  const enrichedActions =
    isEnriched && enrichment ? (
      <Box sx={emptyStateActionsRowSx}>
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
            sx={emptyStateEnrichedActionSx('outlined')}
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
    <Box sx={emptyStateCompactContentSx({ enriched: isEnriched })}>
      <Box
        sx={{
          ...emptyStateInnerStackSx(isEnriched ? 'lg' : 'md'),
          width: isEnriched ? '100%' : undefined,
          maxWidth: isEnriched ? EMPTY_STATE.enrichedMaxWidth : undefined,
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
    <Box sx={emptyStateStandaloneContentSx}>
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
