'use client';

import React from 'react';
import { Fab as MuiFab, Tooltip } from '@mui/material';
import type { FabProps as MuiFabProps } from '@mui/material/Fab';
import { ELEVATION } from '@/styles/theme';

export interface FabProps extends Omit<MuiFabProps, 'children'> {
  /** MUI icon element rendered inside the FAB */
  icon: React.ReactNode;
  /** Optional tooltip label */
  tooltip?: string;
}

/**
 * Figma-aligned FAB component.
 *
 * Wraps MUI `Fab` with Rhesis styling:
 *   - Teal/primary.dark fill, white icon, 56px circular (default size)
 *   - Accepts an optional `tooltip` for accessibility
 */
export function Fab({ icon, tooltip, size = 'large', sx, ...props }: FabProps) {
  const button = (
    <MuiFab
      size={size}
      color="primary"
      sx={{
        bgcolor: 'primary.dark',
        color: '#fff',
        '&:hover': {
          bgcolor: 'primary.main',
        },
        boxShadow: theme => theme.elevation?.xs ?? ELEVATION.xs,
        ...sx,
      }}
      {...props}
    >
      {icon}
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

export default Fab;
