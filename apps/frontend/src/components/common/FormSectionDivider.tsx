'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import { rem } from '@/styles/theme-constants';

export interface FormSectionDividerProps {
  headline: string;
  /** Accepts nodes, not just a string, so callers can embed links. */
  descriptiveText?: React.ReactNode;
}

/**
 * In-card section heading matching Figma Form Section Divider (node 1228:5851).
 */
export default function FormSectionDivider({
  headline,
  descriptiveText,
}: FormSectionDividerProps) {
  return (
    <Box>
      <Typography
        sx={{
          fontSize: rem(18),
          lineHeight: rem(25),
          fontWeight: 700,
          color: theme => theme.palette.greyscale.title,
        }}
      >
        {headline}
      </Typography>
      {descriptiveText ? (
        <Typography
          sx={{
            fontSize: rem(12),
            lineHeight: rem(18),
            color: theme => theme.palette.greyscale.subtitle,
          }}
        >
          {descriptiveText}
        </Typography>
      ) : null}
    </Box>
  );
}
