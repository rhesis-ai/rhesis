'use client';

import * as React from 'react';
import { Chip, type ChipProps } from '@mui/material';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

/**
 * Greyscale badge chip (Figma Chip 818:38074 / detail Input 1413:8344).
 * Used in data grids, detail summaries, and metadata rows.
 */
export function BadgeChip({
  label,
  ...rest
}: Pick<ChipProps, 'label' | 'sx' | 'className'>) {
  return (
    <Chip
      label={label}
      size="small"
      sx={[
        {
          height: 'auto',
          bgcolor: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? '#f3f4f6'
              : GREYSCALE.dark.surface1,
          color: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? GREYSCALE.light.body
              : GREYSCALE.dark.body,
          border: 'none',
          borderRadius: BORDER_RADIUS.xs,
          '& .MuiChip-label': {
            px: '12px',
            py: '2px',
            fontSize: 14,
            lineHeight: '22px',
          },
        },
        ...(Array.isArray(rest.sx) ? rest.sx : rest.sx ? [rest.sx] : []),
      ]}
      {...(rest.className ? { className: rest.className } : {})}
    />
  );
}

export default BadgeChip;
