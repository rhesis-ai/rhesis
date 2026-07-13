'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { SvgIconComponent } from '@mui/icons-material';
import {
  EMPTY_STATE,
  emptyStateCompactTitleSx,
  emptyStateContainedActionSx,
  emptyStateDescriptionSx,
  emptyStateHeaderStackSx,
  emptyStateIconSx,
  emptyStateSectionInsetSx,
} from '@/components/common/entityEmptyStateSx';

export interface SectionEmptyStateProps {
  /** MUI SvgIcon component class (not an element). */
  icon: SvgIconComponent;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  /** When true, shows a leading + icon on the optional CTA button. */
  showAddIcon?: boolean;
  /**
   * When true (default), renders the bordered inset panel for use inside
   * {@link SectionCard}. Set false when {@link SectionCard} is the only
   * card shell (avoids a double border).
   */
  inset?: boolean;
}

/**
 * Empty state inset for {@link SectionCard} body content.
 *
 * Figma: Frontend node 1435:49277 — bordered inner panel (icon, title,
 * secondary description). The section card shell provides the outer card;
 * this component must not add a second shadow or Paper wrapper.
 */
export default function SectionEmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionDisabled = false,
  showAddIcon = false,
  inset = true,
}: SectionEmptyStateProps) {
  return (
    <Box sx={emptyStateSectionInsetSx(inset)}>
      <Box sx={emptyStateHeaderStackSx(true)}>
        <Icon sx={emptyStateIconSx(EMPTY_STATE.iconSize.compact)} />
        <Typography variant="h6" sx={emptyStateCompactTitleSx}>
          {title}
        </Typography>
      </Box>

      {description && (
        <Typography
          variant="body2"
          sx={emptyStateDescriptionSx({ compact: true })}
        >
          {description}
        </Typography>
      )}

      {actionLabel && onAction && (
        <Button
          variant="contained"
          startIcon={showAddIcon ? <AddIcon /> : undefined}
          onClick={onAction}
          disabled={actionDisabled}
          sx={emptyStateContainedActionSx}
        >
          {actionLabel}
        </Button>
      )}
    </Box>
  );
}
