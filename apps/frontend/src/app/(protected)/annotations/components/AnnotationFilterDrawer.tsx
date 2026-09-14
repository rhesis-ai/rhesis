'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import {
  ANNOTATION_ENTITY_LABELS,
  ANNOTATION_ENTITY_TYPES,
  ANNOTATION_TARGET_LABELS,
  ANNOTATION_TARGET_TYPES,
  type AnnotationEntityType,
  type AnnotationTargetType,
} from '@/utils/api-client/interfaces/annotation';

export interface AnnotationFilters {
  rating: '' | 'Pass' | 'Fail';
  entity_type: '' | AnnotationEntityType;
  target_type: '' | AnnotationTargetType;
}

export const EMPTY_ANNOTATION_FILTERS: AnnotationFilters = {
  rating: '',
  entity_type: '',
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

const ENTITY_OPTIONS: { label: string; value: AnnotationEntityType }[] = [
  ANNOTATION_ENTITY_TYPES.TEST_RESULT,
  ANNOTATION_ENTITY_TYPES.TRACE,
].map(value => ({ label: ANNOTATION_ENTITY_LABELS[value], value }));

const TARGET_OPTIONS: { label: string; value: AnnotationTargetType }[] = [
  ANNOTATION_TARGET_TYPES.TEST_RESULT,
  ANNOTATION_TARGET_TYPES.TRACE,
  ANNOTATION_TARGET_TYPES.METRIC,
  ANNOTATION_TARGET_TYPES.TURN,
].map(value => ({ label: ANNOTATION_TARGET_LABELS[value], value }));

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
          {ENTITY_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  entity_type: prev.entity_type === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.entity_type === opt.value)}
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
