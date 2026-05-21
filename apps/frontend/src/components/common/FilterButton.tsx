'use client';

import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import type { IconButtonProps } from '@mui/material/IconButton';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import { BORDER_RADIUS } from '@/styles/theme';

export interface FilterButtonProps extends Omit<
  IconButtonProps,
  'children' | 'color'
> {
  /** When true, shows an active-filter indicator on the button */
  hasActiveFilters?: boolean;
  tooltip?: string;
}

/**
 * Standard filter control for list toolbars and filter drawers.
 * Teal square button with tune icon; optional dot at top-right when filters apply.
 */
export function FilterButton({
  hasActiveFilters = false,
  tooltip = 'Filters',
  'aria-label': ariaLabel = 'Filters',
  size = 'small',
  sx,
  ...props
}: FilterButtonProps) {
  const button = (
    <IconButton
      size={size}
      aria-label={ariaLabel}
      sx={{
        position: 'relative',
        bgcolor: 'primary.main',
        color: '#fff',
        borderRadius: BORDER_RADIUS.sm,
        width: 36,
        height: 36,
        flexShrink: 0,
        '&:hover': { bgcolor: 'primary.dark' },
        ...sx,
      }}
      {...props}
    >
      <TuneOutlinedIcon sx={{ fontSize: 20 }} />
      {hasActiveFilters && (
        <Box
          component="span"
          aria-hidden
          sx={{
            position: 'absolute',
            top: 4,
            right: 4,
            width: 8,
            height: 8,
            borderRadius: '50%',
            bgcolor: 'warning.light',
            border: '2px solid',
            borderColor: 'primary.main',
            pointerEvents: 'none',
          }}
        />
      )}
    </IconButton>
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip}>
        <span>{button}</span>
      </Tooltip>
    );
  }

  return button;
}

export default FilterButton;
