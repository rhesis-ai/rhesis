'use client';

import React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export interface ExperimentFilters {
  visibility: string;
}

export const EMPTY_EXPERIMENT_FILTERS: ExperimentFilters = { visibility: '' };

export function countActiveExperimentFilters(
  filters: ExperimentFilters
): number {
  return filters.visibility ? 1 : 0;
}

export default function ExperimentFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  filters: ExperimentFilters;
  onApply: (filters: ExperimentFilters) => void;
}) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_EXPERIMENT_FILTERS,
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
      <FilterSection title="Visibility">
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {(['', 'private', 'shared'] as const).map(v => (
            <Box
              key={v || 'all'}
              component="button"
              onClick={() => setDraft(d => ({ ...d, visibility: v }))}
              sx={filterChipSx(draft.visibility === v)}
            >
              {v === '' ? 'All' : v.charAt(0).toUpperCase() + v.slice(1)}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
