'use client';

import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

/** A labelled value in the metric page's section cards. */
const InfoRow = React.memo(
  ({ label, children }: { label: string; children: React.ReactNode }) => {
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
        {/* Inherited, not forced on every Typography: the score type and
            scope badges set their own white text. */}
        <Box sx={{ color: theme.palette.text.primary }}>{children}</Box>
      </Box>
    );
  }
);

InfoRow.displayName = 'InfoRow';

export default InfoRow;
