'use client';

import { Box, Typography } from '@mui/material';
import { rem } from '@/styles/theme-constants';

interface SubsectionHeaderProps {
  headline: string;
  description?: string;
}

/** Subsection title inside a detail card (Figma node 1228:5851). */
export default function SubsectionHeader({
  headline,
  description,
}: SubsectionHeaderProps) {
  return (
    <Box sx={{ mb: '20px' }}>
      <Typography
        sx={{
          fontSize: rem(18),
          fontWeight: 700,
          lineHeight: rem(25),
          color: 'text.primary',
        }}
      >
        {headline}
      </Typography>
      {description ? (
        <Typography
          sx={{
            fontSize: rem(12),
            lineHeight: rem(18),
            color: theme => theme.palette.greyscale?.subtitle ?? '#7f8a9b',
          }}
        >
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
