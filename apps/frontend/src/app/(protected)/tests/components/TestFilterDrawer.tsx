'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';

export interface TestFilters {
  /** test_type/type_value equals: 'single_turn' | 'multi_turn' | '' */
  testType: string;
  /** status/name contains */
  status: string;
  /** behavior/name contains */
  behavior: string;
  /** category/name contains */
  category: string;
  /** topic/name contains */
  topic: string;
}

export const EMPTY_TEST_FILTERS: TestFilters = {
  testType: '',
  status: '',
  behavior: '',
  category: '',
  topic: '',
};

export function hasActiveTestFilters(f: TestFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

const TEST_TYPE_OPTIONS = [
  { label: 'Single Turn', value: 'single_turn' },
  { label: 'Multi Turn', value: 'multi_turn' },
] as const;

const textFieldSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: BORDER_RADIUS.sm,
    fontSize: 14,
  },
  '& .MuiOutlinedInput-input': {
    padding: '20px 14px',
  },
};

interface TestFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestFilters;
  onApply: (filters: TestFilters) => void;
}

export default function TestFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TestFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Test Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TEST_TYPE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  testType: prev.testType === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.testType === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Status">
        <TextField
          fullWidth
          placeholder="e.g. Active, Draft…"
          value={draft.status}
          onChange={e =>
            setDraft(prev => ({ ...prev, status: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

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

      <FilterSection title="Category">
        <TextField
          fullWidth
          placeholder="Filter by category name…"
          value={draft.category}
          onChange={e =>
            setDraft(prev => ({ ...prev, category: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

      <FilterSection title="Topic">
        <TextField
          fullWidth
          placeholder="Filter by topic name…"
          value={draft.topic}
          onChange={e => setDraft(prev => ({ ...prev, topic: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
