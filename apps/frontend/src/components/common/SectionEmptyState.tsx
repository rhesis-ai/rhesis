'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { SvgIconComponent } from '@mui/icons-material';
import { BORDER_RADIUS } from '@/styles/theme-constants';

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
}: SectionEmptyStateProps) {
  return (
    <Box
      sx={{
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.md,
        px: { xs: 2, sm: 4, md: '200px' },
        py: '40px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        gap: '20px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <Icon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Typography
          variant="h6"
          sx={{
            fontWeight: 600,
            fontSize: 20,
            lineHeight: '24px',
            color: 'primary.main',
          }}
        >
          {title}
        </Typography>
      </Box>

      {description && (
        <Typography
          variant="body2"
          sx={{
            color: 'text.secondary',
            maxWidth: 480,
            lineHeight: '22px',
          }}
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
          sx={{
            fontWeight: 700,
            fontSize: 18,
            lineHeight: '25px',
            borderRadius: BORDER_RADIUS.md,
            textTransform: 'none',
            px: '20px',
            py: '12px',
          }}
        >
          {actionLabel}
        </Button>
      )}
    </Box>
  );
}
