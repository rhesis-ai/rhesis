'use client';

import { Box, Typography } from '@mui/material';

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
          fontSize: 18,
          fontWeight: 700,
          lineHeight: '25px',
          color: 'text.primary',
        }}
      >
        {headline}
      </Typography>
      {description ? (
        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
            color: theme => theme.palette.greyscale?.subtitle ?? '#7f8a9b',
          }}
        >
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
