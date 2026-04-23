'use client';

import { Chip, useTheme } from '@mui/material';

export function BetaBadge() {
  const theme = useTheme();
  return (
    <Chip
      label="beta"
      size="small"
      variant="outlined"
      color="warning"
      sx={{
        height: theme.spacing(2.25),
        '& .MuiChip-label': {
          px: 0.75,
          fontSize: theme.typography.caption.fontSize,
        },
      }}
    />
  );
}
