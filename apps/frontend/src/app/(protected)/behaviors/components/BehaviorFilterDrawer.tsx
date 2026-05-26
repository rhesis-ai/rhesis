'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';

export type MetricFilter = 'all' | 'has_metrics' | 'no_metrics';

export interface BehaviorFilters {
  metricCount: MetricFilter;
  tagNames: string[];
}

export const EMPTY_BEHAVIOR_FILTERS: BehaviorFilters = {
  metricCount: 'all',
  tagNames: [],
};

export function hasActiveBehaviorFilters(f: BehaviorFilters): boolean {
  return f.metricCount !== 'all' || f.tagNames.length > 0;
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
  /** Unique tag names available across the loaded behaviors. */
  availableTagNames?: string[];
  onApply: (filters: BehaviorFilters) => void;
}

export default function BehaviorFilterDrawer({
  open,
  onClose,
  filters,
  availableTagNames = [],
  onApply,
}: BehaviorFilterDrawerProps) {
  const [draft, setDraft] = React.useState<BehaviorFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_BEHAVIOR_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  const toggleTag = (name: string) => {
    setDraft(prev => {
      const next = prev.tagNames.includes(name)
        ? prev.tagNames.filter(n => n !== name)
        : [...prev.tagNames, name];
      return { ...prev, tagNames: next };
    });
  };

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

      <FilterSection title="Tags">
        {availableTagNames.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No tags yet. Add tags from the behavior edit drawer to group your
            behaviors.
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {availableTagNames.map(name => (
              <Box
                key={name}
                component="button"
                onClick={() => toggleTag(name)}
                sx={filterChipSx(draft.tagNames.includes(name))}
              >
                {name}
              </Box>
            ))}
          </Box>
        )}
      </FilterSection>
    </FilterDrawerShell>
  );
}
