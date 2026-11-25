'use client';

import { Box, Typography } from '@mui/material';
import { BORDER_RADIUS, rem } from '@/styles/theme-constants';

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
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        p: 2,
        mb: 1,
      }}
    >
      <Typography sx={{ fontWeight: 600, fontSize: rem(14), mb: 0.5 }}>
        {title}
      </Typography>
      {description ? (
        <Typography sx={{ fontSize: rem(13), color: 'text.secondary' }}>
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
