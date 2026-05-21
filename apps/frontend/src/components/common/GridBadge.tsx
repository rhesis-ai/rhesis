'use client';

import * as React from 'react';
import { Box, type BoxProps } from '@mui/material';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

export type GridBadgeSize = 'grid' | 'detail';

const BADGE_SIZE_STYLES: Record<
  GridBadgeSize,
  { fontSize: string; lineHeight: string }
> = {
  grid: { fontSize: '12px', lineHeight: '18px' },
  detail: { fontSize: '14px', lineHeight: '22px' },
};

/**
 * Read-only metadata badge (Figma Badge 776:28220, table 1435:46915).
 * Pill-shaped grey label — 12px in grids, 14px on detail pages.
 * User tags use {@link Tag} / {@link BaseTag} — never GridBadge.
 */
export function GridBadge({
  label,
  size = 'grid',
  sx,
  ...rest
}: {
  label: React.ReactNode;
  /** `grid` = 12px (data grids); `detail` = 14px (summary cards, overview tabs). */
  size?: GridBadgeSize;
  sx?: BoxProps['sx'];
} & Omit<BoxProps, 'sx' | 'children'>) {
  const sizeStyles = BADGE_SIZE_STYLES[size];

  return (
    <Box
      component="span"
      sx={[
        {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: '10px',
          py: '2px',
          borderRadius: BORDER_RADIUS.pill,
          bgcolor: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? '#f3f4f6'
              : GREYSCALE.dark.surface1,
          color: (theme: { palette: { mode: string } }) =>
            theme.palette.mode === 'light'
              ? GREYSCALE.light.body
              : GREYSCALE.dark.body,
          fontSize: sizeStyles.fontSize,
          lineHeight: sizeStyles.lineHeight,
          fontWeight: 400,
          whiteSpace: 'nowrap',
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      {...rest}
    >
      {label}
    </Box>
  );
}

export function BadgeRow({
  items,
  size = 'detail',
  maxVisible = 20,
  gap = '8px',
  emptyLabel = 'None',
}: {
  items: string[];
  size?: GridBadgeSize;
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
            <GridBadge key={item} label={item} size={size} />
          ))}
          {remaining > 0 && (
            <GridBadge
              label={`+${remaining}`}
              size={size}
              sx={{ fontWeight: 600 }}
            />
          )}
        </>
      ) : (
        <Box
          component="span"
          sx={{
            fontSize: 14,
            color: theme =>
              theme.palette.mode === 'light'
                ? GREYSCALE.light.subtitle
                : GREYSCALE.dark.subtitle,
          }}
        >
          {emptyLabel}
        </Box>
      )}
    </Box>
  );
}

export default GridBadge;
