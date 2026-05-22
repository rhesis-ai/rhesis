'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';

export interface MetricDrawerFilters {
  type: string[];
  scoreType: string[];
  metricScope: string[];
  behavior: string;
}

export const EMPTY_METRIC_DRAWER_FILTERS: MetricDrawerFilters = {
  type: [],
  scoreType: [],
  metricScope: [],
  behavior: '',
};

export function hasActiveMetricDrawerFilters(f: MetricDrawerFilters): boolean {
  return (
    f.type.length > 0 ||
    f.scoreType.length > 0 ||
    f.metricScope.length > 0 ||
    f.behavior !== ''
  );
}

const METRIC_TYPE_LABELS: Record<string, string> = {
  'custom-prompt': 'LLM Judge',
  'api-call': 'External API',
  'custom-code': 'Script',
  grading: 'Grades',
  framework: 'Framework',
};

export interface MetricFilterOptions {
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
}

const textFieldSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: BORDER_RADIUS.sm,
    fontSize: 14,
  },
  '& .MuiOutlinedInput-input': {
    padding: '20px 14px',
  },
};

interface MetricFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: MetricDrawerFilters;
  filterOptions: MetricFilterOptions;
  onApply: (filters: MetricDrawerFilters) => void;
}

export default function MetricFilterDrawer({
  open,
  onClose,
  filters,
  filterOptions,
  onApply,
}: MetricFilterDrawerProps) {
  const [draft, setDraft] = React.useState<MetricDrawerFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_METRIC_DRAWER_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  const toggleMulti = (
    key: keyof Pick<MetricDrawerFilters, 'type' | 'scoreType' | 'metricScope'>,
    value: string
  ) => {
    setDraft(prev => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value)
          ? arr.filter(v => v !== value)
          : [...arr, value],
      };
    });
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      {filterOptions.type.length > 0 && (
        <FilterSection title="Type">
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {filterOptions.type.map(opt => (
              <Box
                key={opt.type_value}
                component="button"
                onClick={() => toggleMulti('type', opt.type_value)}
                sx={filterChipSx(draft.type.includes(opt.type_value))}
              >
                {METRIC_TYPE_LABELS[opt.type_value] ?? opt.type_value}
              </Box>
            ))}
          </Box>
        </FilterSection>
      )}

      {filterOptions.scoreType.length > 0 && (
        <FilterSection title="Score Type">
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {filterOptions.scoreType.map(opt => (
              <Box
                key={opt.value}
                component="button"
                onClick={() => toggleMulti('scoreType', opt.value)}
                sx={filterChipSx(draft.scoreType.includes(opt.value))}
              >
                {opt.label}
              </Box>
            ))}
          </Box>
        </FilterSection>
      )}

      {filterOptions.metricScope.length > 0 && (
        <FilterSection title="Metric Scope">
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {filterOptions.metricScope.map(opt => (
              <Box
                key={opt.value}
                component="button"
                onClick={() => toggleMulti('metricScope', opt.value)}
                sx={filterChipSx(draft.metricScope.includes(opt.value))}
              >
                {opt.label}
              </Box>
            ))}
          </Box>
        </FilterSection>
      )}

      <FilterSection title="Behavior">
        <TextField
          fullWidth
          placeholder="Filter by behavior name…"
          value={draft.behavior}
          onChange={e =>
            setDraft(prev => ({ ...prev, behavior: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
