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
    <Box sx={{ mb: 2.5 }}>
      <Typography
        variant="h6"
        sx={{ color: 'text.primary' }}
      >
        {headline}
      </Typography>
      {description ? (
        <Typography
          variant="caption"
          sx={{ color: theme => theme.palette.greyscale.subtitle }}
        >
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
