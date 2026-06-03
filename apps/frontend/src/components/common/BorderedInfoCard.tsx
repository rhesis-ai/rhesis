'use client';

import { Box, Typography } from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme';

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
      <Typography
        variant="body2"
        sx={{
          fontWeight: theme => theme.typography.button.fontWeight,
          mb: 0.5,
        }}
      >
        {title}
      </Typography>
      {description ? (
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      ) : null}
    </Box>
  );
}
