'use client';

import React from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { SvgIconComponent } from '@mui/icons-material';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

export interface EntityEmptyStateProps {
  /** MUI SvgIcon component class (not an element). */
  icon: SvgIconComponent;
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
}

/**
 * Figma-aligned empty state used when an entity list is empty.
 *
 * - **Default** (`card=false`): large icon, centered text, optional CTA button.
 * - **Card** (`card=true`): bordered Paper card for section / linked-entity tabs
 *   (Figma node 1435:49277).
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
}: EntityEmptyStateProps) {
  const resolvedIconSize = iconSize ?? (card ? 32 : 64);
  const resolvedShowAddIcon = showAddIcon ?? card;

  const content = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        py: card ? 0 : 10,
        px: card ? { xs: 2, md: '200px' } : 4,
        gap: card ? '20px' : 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: card ? '10px' : 0,
        }}
      >
        <Icon
          sx={{
            fontSize: resolvedIconSize,
            color: 'primary.main',
            opacity: card ? 1 : 0.6,
          }}
        />

        <Typography
          variant="h6"
          sx={{
            fontWeight: card ? 600 : 700,
            fontSize: card ? 20 : undefined,
            lineHeight: card ? '24px' : undefined,
            color: card ? 'primary.main' : 'text.primary',
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
            lineHeight: card ? '22px' : undefined,
          }}
        >
          {description}
        </Typography>
      )}

      {actionLabel && onAction && (
        <Button
          variant={card ? 'outlined' : 'contained'}
          startIcon={resolvedShowAddIcon ? <AddIcon /> : undefined}
          onClick={onAction}
          disabled={actionDisabled}
          sx={
            card
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
              : { mt: 1, fontWeight: 700 }
          }
        >
          {actionLabel}
        </Button>
      )}
    </Box>
  );

  if (!card) return content;

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
      {content}
    </Paper>
  );
}
