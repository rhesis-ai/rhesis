'use client';

import * as React from 'react';
import { TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import ActivityPresenceFiltersSection from '@/components/common/ActivityPresenceFilters';
import {
  EMPTY_ACTIVITY_PRESENCE_FILTERS,
  countActivePresenceFilters,
  hasActivePresenceFilters,
  type ActivityPresenceFilters,
} from '@/components/common/presence-filter';

export interface TestRunFilters {
  /** test_configuration/test_set/name contains */
  testSet: string;
  /** user/name contains (executor) */
  executor: string;
  /** tags contains */
  tag: string;
  tags: ActivityPresenceFilters['tags'];
  comments: ActivityPresenceFilters['comments'];
  tasks: ActivityPresenceFilters['tasks'];
}

export const EMPTY_TEST_RUN_FILTERS: TestRunFilters = {
  testSet: '',
  executor: '',
  tag: '',
  ...EMPTY_ACTIVITY_PRESENCE_FILTERS,
};

export function hasActiveTestRunFilters(f: TestRunFilters): boolean {
  return (
    f.testSet !== '' ||
    f.executor !== '' ||
    f.tag !== '' ||
    hasActivePresenceFilters(f)
  );
}

export function countActiveTestRunFilters(f: TestRunFilters): number {
  return (
    (f.testSet !== '' ? 1 : 0) +
    (f.executor !== '' ? 1 : 0) +
    (f.tag !== '' ? 1 : 0) +
    countActivePresenceFilters(f)
  );
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
        values={{
          tags: draft.tags,
          comments: draft.comments,
          tasks: draft.tasks,
        }}
        onChange={next =>
          setDraft(prev => ({
            ...prev,
            tags: next.tags,
            comments: next.comments,
            tasks: next.tasks,
          }))
        }
      />
    </FilterDrawerShell>
  );
}
