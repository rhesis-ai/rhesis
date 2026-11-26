'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import type { SystemStyleObject } from '@mui/system';
import { rem } from '@/styles/theme-constants';

/** The section headline style, shared with headings that fold (run drawer sections). */
export const formSectionHeadlineSx: SystemStyleObject<Theme> = {
  fontSize: rem(18),
  lineHeight: rem(25),
  fontWeight: 700,
  color: theme => theme.palette.greyscale.title,
};

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
      <Typography sx={formSectionHeadlineSx}>{headline}</Typography>
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
