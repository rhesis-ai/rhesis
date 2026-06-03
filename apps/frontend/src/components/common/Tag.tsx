'use client';

import * as React from 'react';
import { Box, type BoxProps } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';

/** Rectangular tag surface — never pill-shaped (see GridBadge for badges). */
export const tagSurfaceSx: SxProps<Theme> = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  borderRadius: BORDER_RADIUS.xs,
  px: '10px',
  py: '2px',
  height: 26,
  maxWidth: 200,
  bgcolor: theme => theme.palette.greyscale.surface2,
  color: theme => theme.palette.greyscale.body,
  fontSize: (theme: Theme) => theme.typography.body2.fontSize,
  lineHeight: '22px',
  fontWeight: 600,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

/**
 * Read-only tag label (Figma tag chip, no delete icon).
 * Use BaseTag for editable tags; use GridBadge for metadata badges.
 */
export function Tag({
  label,
  sx,
  ...rest
}: {
  label: React.ReactNode;
  sx?: BoxProps['sx'];
} & Omit<BoxProps, 'sx' | 'children'>) {
  return (
    <Box
      component="span"
      sx={[tagSurfaceSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
      {...rest}
    >
      {label}
    </Box>
  );
}

export function TagRow({
  items,
  maxVisible = 20,
  gap = '8px',
  emptyLabel = 'None',
}: {
  items: string[];
  maxVisible?: number;
  gap?: string | number;
  emptyLabel?: string;
}) {
  const visible = items.slice(0, maxVisible);
  const remaining = items.length - maxVisible;

  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        gap,
        minHeight: 28,
        alignItems: 'center',
      }}
    >
      {visible.length > 0 ? (
        <>
          {visible.map(item => (
            <Tag key={item} label={item} />
          ))}
          {remaining > 0 && <Tag label={`+${remaining}`} />}
        </>
      ) : (
        <Box
          component="span"
          sx={{
            fontSize: (theme: Theme) => theme.typography.body2.fontSize,
            color: theme => theme.palette.greyscale.subtitle,
          }}
        >
          {emptyLabel}
        </Box>
      )}
    </Box>
  );
}

export default Tag;
