'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';

export const HISTORY_RANGE_OPTIONS: { months: number; label: string }[] = [
  { months: 3, label: '3M' },
  { months: 6, label: '6M' },
  { months: 12, label: '12M' },
];

interface UsageOverTimeFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  months: number;
  onChange: (months: number) => void;
}

// No Apply/Reset footer: picking a timespan has immediate effect on the
// charts underneath, same as before this moved into a drawer.
export default function UsageOverTimeFilterDrawer({
  open,
  onClose,
  months,
  onChange,
}: UsageOverTimeFilterDrawerProps) {
  return (
    <FilterDrawerShell open={open} onClose={onClose}>
      <FilterSection title="Timespan">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {HISTORY_RANGE_OPTIONS.map(option => (
            <Box
              key={option.months}
              component="button"
              type="button"
              onClick={() => onChange(option.months)}
              sx={filterChipSx(months === option.months)}
            >
              {option.label}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
