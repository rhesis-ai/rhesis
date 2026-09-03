'use client';

import * as React from 'react';
import { Autocomplete, Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerTextFieldSx,
} from '@/components/common/FilterDrawer';
import { useRunTestSets, useTags, useUsers } from '@/hooks/useLookups';
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

  // Suggestions, fetched only while the drawer is open. Typing still works
  // for values that aren't listed (freeSolo).
  const { data: rawTestSets, isLoading: loadingTestSets } =
    useRunTestSets(open);
  const { data: rawUsers, isLoading: loadingUsers } = useUsers(open);
  const { data: rawTags, isLoading: loadingTags } = useTags(open);
  const loadingOptions = loadingTestSets || loadingUsers || loadingTags;

  const testSetOptions = React.useMemo(
    () => (rawTestSets ?? []).map(ts => ts.name).filter(Boolean),
    [rawTestSets]
  );
  const executorOptions = React.useMemo(
    () =>
      (rawUsers ?? [])
        .map(
          user =>
            user.name ||
            `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
            user.email
        )
        .filter(Boolean),
    [rawUsers]
  );
  const tagOptions = React.useMemo(
    () => (rawTags ?? []).map(tag => tag.name).filter(Boolean),
    [rawTags]
  );

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const renderAutocomplete = (
    title: string,
    field: keyof Pick<TestRunFilters, 'testSet' | 'executor' | 'tag'>,
    options: string[],
    placeholder: string
  ) => (
    <FilterSection title={title}>
      <Autocomplete
        freeSolo
        options={options}
        value={draft[field] || null}
        loading={loadingOptions}
        onChange={(_, value) =>
          setDraft(prev => ({ ...prev, [field]: value || '' }))
        }
        onInputChange={(_, value) =>
          setDraft(prev => ({ ...prev, [field]: value }))
        }
        renderInput={params => (
          <TextField {...params} placeholder={placeholder} sx={textFieldSx} />
        )}
      />
    </FilterSection>
  );

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

      {renderAutocomplete(
        'Test Set',
        'testSet',
        testSetOptions,
        'Select test set…'
      )}
      {renderAutocomplete(
        'Executor',
        'executor',
        executorOptions,
        'Select executor…'
      )}
      {renderAutocomplete('Tags', 'tag', tagOptions, 'Select tag…')}

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
