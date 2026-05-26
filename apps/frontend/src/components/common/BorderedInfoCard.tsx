'use client';

import { Box, Typography } from '@mui/material';
import { GREYSCALE } from '@/styles/theme';

interface BorderedInfoCardProps {
  title: string;
  description?: string;
}

/** Compact bordered card for read-only nested info on detail pages. */
export default function BorderedInfoCard({
  title,
  description,
}: BorderedInfoCardProps) {
  return (
    <Box
      sx={{
        border: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        borderRadius: '8px',
        p: 2,
        mb: 1,
      }}
    >
      <Typography sx={{ fontWeight: 600, fontSize: 14, mb: 0.5 }}>
        {title}
      </Typography>
      {description ? (
        <Typography sx={{ fontSize: 13, color: 'text.secondary' }}>
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
