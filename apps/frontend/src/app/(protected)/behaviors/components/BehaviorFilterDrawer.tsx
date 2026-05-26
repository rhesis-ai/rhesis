'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export type MetricFilter = 'all' | 'has_metrics' | 'no_metrics';

export interface BehaviorFilters {
  metricCount: MetricFilter;
}

export const EMPTY_BEHAVIOR_FILTERS: BehaviorFilters = {
  metricCount: 'all',
};

export function hasActiveBehaviorFilters(f: BehaviorFilters): boolean {
  return f.metricCount !== 'all';
}

const METRIC_OPTIONS: { value: MetricFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'has_metrics', label: 'Has Metrics' },
  { value: 'no_metrics', label: 'No Metrics' },
];

interface BehaviorFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: BehaviorFilters;
  onApply: (filters: BehaviorFilters) => void;
}

export default function BehaviorFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: BehaviorFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_BEHAVIOR_FILTERS,
    onApply,
    onClose
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Metrics">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {METRIC_OPTIONS.map(({ value, label }) => (
            <Box
              key={value}
              component="button"
              onClick={() =>
                setDraft(prev => ({ ...prev, metricCount: value }))
              }
              sx={filterChipSx(draft.metricCount === value)}
            >
              {label}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
