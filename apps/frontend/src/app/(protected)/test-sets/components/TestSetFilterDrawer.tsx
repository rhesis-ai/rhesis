'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { TEST_TYPES } from '@/constants/test-types';

// ── Filter state ────────────────────────────────────────────────────────────────

export interface TestSetFilters {
  /** test_set_type/type_value equals */
  testSetType: string;
  /** status/name contains */
  status: string;
  /** user/name contains */
  creator: string;
  /** tags/name contains */
  tag: string;
}

export const EMPTY_TEST_SET_FILTERS: TestSetFilters = {
  testSetType: '',
  status: '',
  creator: '',
  tag: '',
};

export function hasActiveTestSetFilters(f: TestSetFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

// ── Constants ───────────────────────────────────────────────────────────────────

const TEST_SET_TYPE_OPTIONS = [
  { label: 'Single Turn', value: TEST_TYPES.SINGLE_TURN },
  { label: 'Multi Turn', value: TEST_TYPES.MULTI_TURN },
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

// ── Main component ──────────────────────────────────────────────────────────────

interface TestSetFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestSetFilters;
  onApply: (filters: TestSetFilters) => void;
}

export default function TestSetFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TestSetFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestSetFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_SET_FILTERS);

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
      title="Filter"
    >
      {/* Test Set Type */}
      <FilterSection title="Test Set Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TEST_SET_TYPE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  testSetType: prev.testSetType === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.testSetType === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      {/* Status */}
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

      {/* Creator */}
      <FilterSection title="Creator">
        <TextField
          fullWidth
          placeholder="Filter by creator name…"
          value={draft.creator}
          onChange={e =>
            setDraft(prev => ({ ...prev, creator: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

      {/* Tag */}
      <FilterSection title="Tag">
        <TextField
          fullWidth
          placeholder="Filter by tag name…"
          value={draft.tag}
          onChange={e => setDraft(prev => ({ ...prev, tag: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
