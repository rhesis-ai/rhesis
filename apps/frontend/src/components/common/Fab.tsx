'use client';

import React from 'react';
import { Box, CircularProgress, Fab as MuiFab, Tooltip } from '@mui/material';
import type { BoxProps } from '@mui/material/Box';
import type { FabProps as MuiFabProps } from '@mui/material/Fab';
import { ELEVATION, FAB_GROUP_GAP } from '@/styles/theme';

export { FAB_GROUP_GAP };
export { default as FabAddIcon } from './FabAddIcon';

/** Figma FAB icon slot — 32×32 with 24×24 glyph (12.5% inset) */
const fabIconSlotSx = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 32,
  height: 32,
  flexShrink: 0,
  lineHeight: 0,
  '& > .MuiSvgIcon-root': {
    width: 24,
    height: 24,
    fontSize: 24,
  },
} as const;

/** Shared FAB surface styles (56px circle, 12px padding, primary fill, elevation) */
export const fabButtonSx = {
  bgcolor: 'primary.main',
  color: 'primary.contrastText',
  width: 56,
  height: 56,
  minWidth: 56,
  minHeight: 56,
  padding: '12px',
  boxSizing: 'border-box',
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
 * Figma-aligned FAB component (node 1639:10079).
 *
 * 56px circle, 12px padding, 32px icon slot, primary fill, elevation XS.
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
      {loading ? (
        <CircularProgress size={24} sx={{ color: '#fff' }} />
      ) : (
        <Box component="span" sx={fabIconSlotSx}>
          {icon}
        </Box>
      )}
    </MuiFab>
  );

  if (tooltip) {
    return (
      <Tooltip title={tooltip} placement="bottom">
        {/* Span needed so tooltip fires on hover even when the FAB is disabled */}
        <span style={{ display: 'inline-flex' }}>{button}</span>
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
