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
  /** Number of active filters to display on the badge (overrides plain dot when > 0) */
  activeFilterCount?: number;
  tooltip?: string;
}

/**
 * Standard filter control for list toolbars and filter drawers.
 * Teal square button with tune icon; shows a numeric count badge when filters are active.
 */
export function FilterButton({
  hasActiveFilters = false,
  activeFilterCount,
  tooltip = 'Filters',
  'aria-label': ariaLabel = 'Filters',
  size = 'small',
  sx,
  ...props
}: FilterButtonProps) {
  const count = activeFilterCount ?? 0;
  const showBadge = count > 0 || hasActiveFilters;

  const button = (
    <IconButton
      size={size}
      aria-label={ariaLabel}
      sx={{
        position: 'relative',
        bgcolor: 'primary.main',
        color: 'primary.contrastText',
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
      {showBadge && (
        <Box
          component="span"
          aria-label={count > 0 ? `${count} active filters` : 'Active filters'}
          sx={{
            position: 'absolute',
            top: -6,
            right: -6,
            minWidth: 18,
            height: 18,
            px: count > 9 ? '4px' : 0,
            borderRadius: '50%',
            bgcolor: 'background.paper',
            color: 'primary.main',
            fontSize: 11,
            fontWeight: 700,
            lineHeight: '18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            border: '1.5px solid',
            borderColor: 'primary.main',
          }}
        >
          {count > 0 ? count : null}
        </Box>
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
