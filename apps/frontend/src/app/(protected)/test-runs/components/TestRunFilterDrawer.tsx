'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerTextFieldSx,
} from '@/components/common/FilterDrawer';
import ActivityPresenceFiltersSection from '@/components/common/ActivityPresenceFilters';
import {
  countActivePresenceFilters,
  hasActivePresenceFilters,
  type ActivityPresenceFilters,
} from '@/components/common/presence-filter';

export type RunKindFilter = 'all' | 'tests' | 'experiments';

export interface TestRunFilters {
  /** test_configuration/test_set/name contains */
  testSet: string;
  /** user/name contains (executor) */
  executor: string;
  /** tags contains */
  tag: string;
  /** surfaced as `has_experiment` via `extraParams`, see list.ts */
  runKind: RunKindFilter;
  tags: ActivityPresenceFilters['tags'];
  reviews: ActivityPresenceFilters['reviews'];
  comments: ActivityPresenceFilters['comments'];
  tasks: ActivityPresenceFilters['tasks'];
}

export const EMPTY_TEST_RUN_FILTERS: TestRunFilters = {
  testSet: '',
  executor: '',
  tag: '',
  runKind: 'all',
  tags: 'all',
  reviews: 'all',
  comments: 'all',
  tasks: 'all',
};

export function hasActiveTestRunFilters(f: TestRunFilters): boolean {
  return (
    f.testSet !== '' ||
    f.executor !== '' ||
    f.tag !== '' ||
    f.runKind !== 'all' ||
    hasActivePresenceFilters(f)
  );
}

export function countActiveTestRunFilters(f: TestRunFilters): number {
  return (
    (f.testSet !== '' ? 1 : 0) +
    (f.executor !== '' ? 1 : 0) +
    (f.tag !== '' ? 1 : 0) +
    (f.runKind !== 'all' ? 1 : 0) +
    countActivePresenceFilters(f)
  );
}

const RUN_KIND_OPTIONS: { label: string; value: RunKindFilter }[] = [
  { label: 'Tests', value: 'tests' },
  { label: 'Experiments', value: 'experiments' },
];

const textFieldSx = filterDrawerTextFieldSx;

interface TestRunFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestRunFilters;
  onApply: (filters: TestRunFilters) => void;
}

export default function TestRunFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TestRunFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestRunFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_RUN_FILTERS);

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
      <FilterSection title="Run Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {RUN_KIND_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  runKind: prev.runKind === opt.value ? 'all' : opt.value,
                }))
              }
              sx={filterChipSx(draft.runKind === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Test Set">
        <TextField
          fullWidth
          placeholder="Filter by test set name…"
          value={draft.testSet}
          onChange={e =>
            setDraft(prev => ({ ...prev, testSet: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

      <FilterSection title="Executor">
        <TextField
          fullWidth
          placeholder="Filter by executor name…"
          value={draft.executor}
          onChange={e =>
            setDraft(prev => ({ ...prev, executor: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

      <FilterSection title="Tags">
        <TextField
          fullWidth
          placeholder="Filter by tag name…"
          value={draft.tag}
          onChange={e => setDraft(prev => ({ ...prev, tag: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>

      <ActivityPresenceFiltersSection
        showReviews
        values={{
          tags: draft.tags,
          reviews: draft.reviews,
          comments: draft.comments,
          tasks: draft.tasks,
        }}
        onChange={next =>
          setDraft(prev => ({
            ...prev,
            tags: next.tags,
            reviews: next.reviews ?? 'all',
            comments: next.comments,
            tasks: next.tasks,
          }))
        }
      />
    </FilterDrawerShell>
  );
}
