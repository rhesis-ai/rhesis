'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';

interface EntityEmptyStateProps {
  /** MUI SvgIcon component class (not an element) */
  icon: SvgIconComponent;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionDisabled?: boolean;
}

/**
 * Figma-aligned empty state card used when an entity list is empty.
 * Shows a large teal icon, a title, an optional description, and an
 * optional primary CTA button.
 */
export default function EntityEmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionDisabled = false,
}: EntityEmptyStateProps) {
  return (
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
      <Icon sx={{ fontSize: 64, color: 'primary.main', opacity: 0.6 }} />

      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        {title}
      </Typography>

      {description && (
        <Typography
          variant="body2"
          sx={{ color: 'text.secondary', maxWidth: 480 }}
        >
          {description}
        </Typography>
      )}

      {actionLabel && onAction && (
        <Button
          variant="contained"
          onClick={onAction}
          disabled={actionDisabled}
          sx={{ mt: 1, fontWeight: 700 }}
        >
          {actionLabel}
        </Button>
      )}
    </Box>
  );
}
