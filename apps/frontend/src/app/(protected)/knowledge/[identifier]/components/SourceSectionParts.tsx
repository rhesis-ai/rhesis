'use client';

import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import type { Theme } from '@mui/material/styles';

/** The surface of the source page's cards. */
export const sourcePaperSx = (theme: Theme) => ({
  p: theme.spacing(3),
  borderRadius: theme.spacing(1),
  bgcolor: theme.palette.background.paper,
  boxShadow: theme.shadows[1],
});

export function SectionHeader({ title }: { title: string }) {
  const theme = useTheme();
  return (
    <Typography
      variant="h6"
      sx={{
        fontWeight: theme.typography.fontWeightMedium,
        color: theme.palette.text.primary,
      }}
    >
      {title}
    </Typography>
  );
}

export function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const theme = useTheme();
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: theme.spacing(1),
        py: theme.spacing(1),
      }}
    >
      <Typography
        variant="subtitle2"
        sx={{
          color: theme.palette.text.secondary,
          fontWeight: theme.typography.fontWeightMedium,
          letterSpacing: '0.02em',
        }}
      >
        {label}
      </Typography>
      <Box
        sx={{
          '& .MuiTypography-root': {
            color: theme.palette.text.primary,
          },
        }}
      >
        {children}
      </Box>
    </Box>
  );
}
