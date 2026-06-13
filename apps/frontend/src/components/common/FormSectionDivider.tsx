'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';

export interface FormSectionDividerProps {
  headline: string;
  descriptiveText?: string;
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
          fontSize: 18,
          lineHeight: '25px',
          fontWeight: 700,
          color: theme => theme.palette.greyscale.title,
        }}
      >
        {headline}
      </Typography>
      {descriptiveText ? (
        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: theme => theme.palette.greyscale.subtitle,
          }}
        >
          {descriptiveText}
        </Typography>
      ) : null}
    </Box>
  );
}
