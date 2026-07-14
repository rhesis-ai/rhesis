'use client';

import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { alpha, type Theme } from '@mui/material/styles';
import { ELEVATION, BORDER_RADIUS } from '@/styles/theme';

export type SectionCardVariant = 'default' | 'danger';

export interface SectionCardProps {
  /** When omitted (along with subtitle and actions), the header row is skipped entirely */
  title?: string;
  /** Optional subtitle below the title (Body S, secondary). Accepts a string or React node for inline links. */
  subtitle?: React.ReactNode;
  /** Header actions (e.g. Edit button, FAB) */
  actions?: React.ReactNode;
  variant?: SectionCardVariant;
  /** Makes the entire header row clickable (e.g. for collapsible sections) */
  onHeaderClick?: () => void;
  children?: React.ReactNode;
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
      theme.palette.mode === 'light'
        ? '#ffffff'
        : theme.palette.greyscale.surface1,
    border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
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
  onHeaderClick,
  children,
}: SectionCardProps) {
  const titleColor = variant === 'danger' ? 'error.main' : 'primary.main';
  const hasHeader = Boolean(title || subtitle || actions);

  return (
    <Paper elevation={0} sx={cardSx(variant)}>
      {hasHeader && (
        <Box
          onClick={onHeaderClick}
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
            mb: 3,
            ...(onHeaderClick && { cursor: 'pointer', userSelect: 'none' }),
          }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>
            {title && (
              <Typography
                variant="h6"
                sx={{ fontWeight: 600, color: titleColor }}
              >
                {title}
              </Typography>
            )}
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
            <Box
              sx={{
                display: 'flex',
                flexShrink: 0,
                alignItems: 'center',
                gap: '10px',
              }}
            >
              {actions}
            </Box>
          )}
        </Box>
      )}
      {children}
    </Paper>
  );
}

/** Paper shell for overview tables (Tests, Team members grid). */
export const overviewTablePaperSx = {
  width: '100%',
  borderRadius: BORDER_RADIUS.md,
  boxShadow: ELEVATION.xs,
  border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
  overflow: 'hidden' as const,
};

/**
 * Figma node 1640:23151 — table grid nested inside SectionCard. The section
 * card supplies the outer border/shadow; this only styles the inner rows.
 */
export const overviewTableInnerSx = {
  width: '100%',
  overflow: 'hidden' as const,
  '& .MuiTable-root': {
    tableLayout: 'fixed',
    borderCollapse: 'separate',
    borderSpacing: 0,
  },
  '& .MuiTableCell-root': {
    borderBottom: 'none',
  },
} as const;

export default SectionCard;
