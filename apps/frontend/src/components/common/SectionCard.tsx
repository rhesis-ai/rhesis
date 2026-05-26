'use client';

import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';
import { GREYSCALE, ELEVATION, BORDER_RADIUS } from '@/styles/theme';

export type SectionCardVariant = 'default' | 'danger';

export interface SectionCardProps {
  title: string;
  /** Optional subtitle below the title (Body S, secondary) */
  subtitle?: string;
  /** Header actions (e.g. Edit button, FAB) */
  actions?: React.ReactNode;
  variant?: SectionCardVariant;
  children: React.ReactNode;
}

function cardSx(variant: SectionCardVariant) {
  const shared = {
    p: '30px',
    mb: 3,
    borderRadius: BORDER_RADIUS.md,
    boxShadow: (theme: Theme) =>
      theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
  };

  if (variant === 'danger') {
    return {
      ...shared,
      border: '1px solid',
      borderColor: 'error.light',
      bgcolor: (theme: Theme) => alpha(theme.palette.error.main, 0.05),
    };
  }

  return {
    ...shared,
    bgcolor: (theme: Theme) =>
      theme.palette.mode === 'light' ? '#ffffff' : GREYSCALE.dark.surface1,
    border: (theme: Theme) =>
      `1px solid ${
        theme.palette.mode === 'light'
          ? GREYSCALE.light.border
          : GREYSCALE.dark.border
      }`,
  };
}

/**
 * Bordered content card matching the Figma detail-page section pattern.
 * Used by EditableSection, org settings EE blocks, and team overview sections.
 */
export function SectionCard({
  title,
  subtitle,
  actions,
  variant = 'default',
  children,
}: SectionCardProps) {
  const titleColor = variant === 'danger' ? 'error.main' : 'primary.main';

  return (
    <Paper elevation={0} sx={cardSx(variant)}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
          mb: subtitle || actions ? 3 : 3,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, color: titleColor }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography
              variant="body2"
              sx={{ mt: 0.5, color: 'text.secondary' }}
            >
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && (
          <Box sx={{ display: 'flex', flexShrink: 0, alignItems: 'center' }}>
            {actions}
          </Box>
        )}
      </Box>
      {children}
    </Paper>
  );
}

/** Paper shell for overview tables (Tests, Team members grid). */
export const overviewTablePaperSx = {
  width: '100%',
  borderRadius: BORDER_RADIUS.md,
  boxShadow: ELEVATION.xs,
  border: (theme: Theme) =>
    `1px solid ${
      theme.palette.mode === 'light'
        ? GREYSCALE.light.border
        : GREYSCALE.dark.border
    }`,
  overflow: 'hidden' as const,
};

export default SectionCard;
