'use client';

import React from 'react';
import { Typography } from '@mui/material';

interface UsageCellProps {
  /** The figure, or null/undefined when the backend had none to give. */
  value: number | null | undefined;
  format: (value: number) => string;
  /** Native title, e.g. the input/output split behind a total. */
  title?: string;
}

/**
 * One token or cost figure in a grid, or a dash when it is genuinely unknown.
 *
 * Emptiness is keyed on null/undefined, never on falsiness. A trace priced at zero -- a
 * free tier, a comped deployment -- costs a real, knowable nothing, and the backend
 * sends that 0 on purpose; a truthy check would turn it back into "we have no idea".
 * The two are different claims and the grid has to keep them apart.
 *
 * Shared by the traces grid and the test runs grid so one cell cannot start hiding a
 * zero the other shows.
 */
export default function UsageCell({ value, format, title }: UsageCellProps) {
  if (value === null || value === undefined) {
    return (
      <Typography variant="body2" sx={{ color: 'text.disabled' }}>
        —
      </Typography>
    );
  }

  return (
    <Typography
      variant="body2"
      sx={{ fontVariantNumeric: 'tabular-nums' }}
      title={title}
    >
      {format(value)}
    </Typography>
  );
}
