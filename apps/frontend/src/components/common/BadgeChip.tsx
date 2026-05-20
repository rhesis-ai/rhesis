'use client';

import * as React from 'react';
import { Chip, type ChipProps } from '@mui/material';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

/**
 * Greyscale badge chip used inside data grids to display metadata values
 * (type, behavior, category, topic, etc.).
 *
 * Consistent visual: filled greyscale surface, no border, pill radius,
 * caption-size font — light and dark mode aware.
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
          bgcolor: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? GREYSCALE.light.surface2
              : GREYSCALE.dark.surface1,
          color: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? GREYSCALE.light.body
              : GREYSCALE.dark.body,
          border: 'none',
          borderRadius: BORDER_RADIUS.pill,
          fontSize: (theme: {
            typography: { caption: { fontSize: string } };
          }) => theme.typography.caption.fontSize,
          lineHeight: '18px',
        },
        ...(Array.isArray(rest.sx) ? rest.sx : rest.sx ? [rest.sx] : []),
      ]}
      {...(rest.className ? { className: rest.className } : {})}
    />
  );
}

export default BadgeChip;
