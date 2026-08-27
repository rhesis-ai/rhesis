'use client';

import React from 'react';
import { Box, Chip } from '@mui/material';
import { getReviewBand } from '@/constants/outcomes';

interface BandChipProps {
  /** Pass rate as a percentage (0-100), or null when nothing has resolved. */
  passRate: number | null;
}

/**
 * The "OK / Watch / Needs Review" verdict for a row's pass rate.
 *
 * Bands come from the shared `getReviewBand` scale, so this chip can never
 * disagree with the pass rate rendered beside it.
 */
export default function BandChip({ passRate }: BandChipProps) {
  // Nothing resolved yet -- an empty cell, not an "OK". The wrapper still
  // renders: in the verdict grid this occupies a fixed column track, and
  // returning null would slide the strip into the status column.
  if (passRate === null) return <Box sx={{ overflow: 'hidden' }} />;

  const band = getReviewBand(passRate);

  return (
    <Box sx={{ overflow: 'hidden' }}>
      <Chip
        label={band.label}
        size="small"
        color={band.colorKey}
        sx={{ maxWidth: '100%' }}
      />
    </Box>
  );
}
