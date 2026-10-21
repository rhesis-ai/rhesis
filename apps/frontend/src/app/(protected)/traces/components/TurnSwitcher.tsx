'use client';

import { Box, IconButton, Typography } from '@mui/material';
import { ChevronLeftIcon, ChevronRightIcon } from '@/components/icons';

interface TurnSwitcherProps {
  /** Zero-based index of the turn on screen, or null when no turn is selected. */
  index: number | null;
  count: number;
  onChange: (index: number) => void;
}

export default function TurnSwitcher({
  index,
  count,
  onChange,
}: TurnSwitcherProps) {
  const hasPrevious = index !== null && index > 0;
  const hasNext = index !== null && index < count - 1;

  return (
    <Box
      role="group"
      aria-label="Conversation turns"
      sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
    >
      <IconButton
        size="small"
        aria-label="Previous turn"
        disabled={!hasPrevious}
        onClick={() => index !== null && onChange(index - 1)}
      >
        <ChevronLeftIcon fontSize="small" />
      </IconButton>
      <Typography variant="body2" color="text.secondary" aria-live="polite">
        {index === null ? `${count} turns` : `Turn ${index + 1} of ${count}`}
      </Typography>
      <IconButton
        size="small"
        aria-label="Next turn"
        disabled={!hasNext}
        onClick={() => index !== null && onChange(index + 1)}
      >
        <ChevronRightIcon fontSize="small" />
      </IconButton>
    </Box>
  );
}
