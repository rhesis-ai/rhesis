'use client';

import React from 'react';
import { Box, CircularProgress, Fab as MuiFab, Tooltip } from '@mui/material';
import type { BoxProps } from '@mui/material/Box';
import type { FabProps as MuiFabProps } from '@mui/material/Fab';
import { ELEVATION, FAB_GROUP_GAP } from '@/styles/theme';

export { FAB_GROUP_GAP };

/** Shared FAB surface styles (56px circle, primary fill, elevation) */
export const fabButtonSx = {
  bgcolor: 'primary.main',
  color: '#fff',
  width: 56,
  height: 56,
  boxShadow: ELEVATION.xs,
  '&:hover': {
    bgcolor: 'primary.dark',
  },
  '&:active': {
    boxShadow: ELEVATION.xs,
  },
} as const;

export interface FabProps extends Omit<MuiFabProps, 'children'> {
  /** MUI icon element rendered inside the FAB */
  icon: React.ReactNode;
  /** Optional tooltip label */
  tooltip?: string;
  /** Shows a spinner instead of the icon */
  loading?: boolean;
}

/**
 * Figma-aligned FAB component.
 *
 * Wraps MUI `Fab` with Rhesis styling:
 *   - Teal/primary.main fill, white icon, 56px circular
 *   - Accepts an optional `tooltip` for accessibility
 */
export function Fab({
  icon,
  tooltip,
  loading = false,
  size = 'large',
  disabled,
  sx,
  ...props
}: FabProps) {
  const button = (
    <MuiFab
      size={size}
      color="primary"
      disabled={disabled || loading}
      sx={{
        ...fabButtonSx,
        boxShadow: theme => theme.elevation?.xs ?? ELEVATION.xs,
        ...sx,
      }}
      {...props}
    >
      {loading ? <CircularProgress size={24} sx={{ color: '#fff' }} /> : icon}
    </MuiFab>
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip} placement="bottom">
        {button}
      </Tooltip>
    );
  }

  return button;
}

export interface FabGroupProps extends BoxProps {
  children: React.ReactNode;
}

/**
 * Horizontal row for page-header FAB actions.
 * Gap is fixed at 20px per Figma (see FAB_GROUP_GAP).
 */
export function FabGroup({ children, sx, ...props }: FabGroupProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        ...sx,
        gap: FAB_GROUP_GAP,
      }}
      {...props}
    >
      {children}
    </Box>
  );
}

export default Fab;
