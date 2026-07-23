'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import type { AnnotationSource } from '@/utils/api-client/interfaces/annotation';

export interface AnnotationFilters {
  rating: '' | 'Pass' | 'Fail';
  source: '' | AnnotationSource;
  target_type: '' | 'test_result' | 'trace' | 'metric' | 'turn';
}

export const EMPTY_ANNOTATION_FILTERS: AnnotationFilters = {
  rating: '',
  source: '',
  target_type: '',
};

export function hasActiveAnnotationFilters(f: AnnotationFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

export function countActiveAnnotationFilters(f: AnnotationFilters): number {
  return Object.values(f).filter(v => v !== '').length;
}

const RATING_OPTIONS: { label: string; value: 'Pass' | 'Fail' }[] = [
  { label: 'Passed', value: 'Pass' },
  { label: 'Failed', value: 'Fail' },
];

const SOURCE_OPTIONS: { label: string; value: AnnotationSource }[] = [
  { label: 'Test Result', value: 'test_result' },
  { label: 'Trace', value: 'trace' },
];

const TARGET_OPTIONS: {
  label: string;
  value: 'test_result' | 'trace' | 'metric' | 'turn';
}[] = [
  { label: 'Output', value: 'test_result' },
  { label: 'Trace', value: 'trace' },
  { label: 'Metric', value: 'metric' },
  { label: 'Turn', value: 'turn' },
];

interface AnnotationFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: AnnotationFilters;
  onApply: (filters: AnnotationFilters) => void;
}

export default function AnnotationFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: AnnotationFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_ANNOTATION_FILTERS,
    onApply,
    onClose
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      <FilterSection title="Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {SOURCE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  source: prev.source === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.source === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Rating">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {RATING_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  rating: prev.rating === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.rating === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Target">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TARGET_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  target_type: prev.target_type === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.target_type === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
