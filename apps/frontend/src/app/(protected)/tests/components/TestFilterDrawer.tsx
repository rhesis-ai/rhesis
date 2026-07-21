'use client';

import * as React from 'react';
import { Autocomplete, Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerTextFieldSx,
} from '@/components/common/FilterDrawer';
import { filterUniqueValidOptions } from '@/components/common/BaseDrawer';
import { ENTITY_TYPES } from '@/utils/api-client/config';
import { TEST_TYPE_FILTER_OPTIONS } from '@/constants/test-types';
import {
  useStatuses,
  useBehaviors,
  useCategories,
  useTopics,
} from '@/hooks/useLookups';
import ActivityPresenceFiltersSection from '@/components/common/ActivityPresenceFilters';
import { EntityType } from '@/types/entity-type';
import {
  EMPTY_ACTIVITY_PRESENCE_FILTERS,
  countActivePresenceFilters,
  hasActivePresenceFilters,
  type ActivityPresenceFilters,
} from '@/components/common/presence-filter';

export interface TestFilters {
  /** test_type/type_value equals: Single-Turn | Multi-Turn | '' */
  testType: string;
  /** status/name equals */
  status: string;
  /** behavior/name equals */
  behavior: string;
  /** category/name equals */
  category: string;
  /** topic/name equals */
  topic: string;
  tags: ActivityPresenceFilters['tags'];
  comments: ActivityPresenceFilters['comments'];
  tasks: ActivityPresenceFilters['tasks'];
}

export const EMPTY_TEST_FILTERS: TestFilters = {
  testType: '',
  status: '',
  behavior: '',
  category: '',
  topic: '',
  ...EMPTY_ACTIVITY_PRESENCE_FILTERS,
};

export function hasActiveTestFilters(f: TestFilters): boolean {
  return (
    f.testType !== '' ||
    f.status !== '' ||
    f.behavior !== '' ||
    f.category !== '' ||
    f.topic !== '' ||
    hasActivePresenceFilters(f)
  );
}

export function countActiveTestFilters(f: TestFilters): number {
  return (
    (f.testType !== '' ? 1 : 0) +
    (f.status !== '' ? 1 : 0) +
    (f.behavior !== '' ? 1 : 0) +
    (f.category !== '' ? 1 : 0) +
    (f.topic !== '' ? 1 : 0) +
    countActivePresenceFilters(f)
  );
}

const textFieldSx = filterDrawerTextFieldSx;

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

  const { data: rawStatuses, isLoading: loadingStatuses } = useStatuses(
    ENTITY_TYPES.test,
    open
  );
  const { data: rawBehaviors, isLoading: loadingBehaviors } =
    useBehaviors(open);
  const { data: rawCategories, isLoading: loadingCategories } = useCategories(
    EntityType.TEST,
    open
  );
  const { data: rawTopics, isLoading: loadingTopics } = useTopics(
    EntityType.TEST,
    open
  );
  const loadingOptions =
    loadingStatuses || loadingBehaviors || loadingCategories || loadingTopics;

  const statusOptions = React.useMemo(
    () => filterUniqueValidOptions(rawStatuses ?? []).map(s => s.name),
    [rawStatuses]
  );
  const behaviorOptions = React.useMemo(
    () => filterUniqueValidOptions(rawBehaviors ?? []).map(b => b.name),
    [rawBehaviors]
  );
  const categoryOptions = React.useMemo(
    () => filterUniqueValidOptions(rawCategories ?? []).map(c => c.name),
    [rawCategories]
  );
  const topicOptions = React.useMemo(
    () => filterUniqueValidOptions(rawTopics ?? []).map(t => t.name),
    [rawTopics]
  );

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  const renderAutocomplete = (
    title: string,
    field: keyof Pick<
      TestFilters,
      'status' | 'behavior' | 'category' | 'topic'
    >,
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

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Test Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TEST_TYPE_FILTER_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
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

      {renderAutocomplete('Status', 'status', statusOptions, 'Select status…')}
      {renderAutocomplete(
        'Behavior',
        'behavior',
        behaviorOptions,
        'Select behavior…'
      )}
      {renderAutocomplete(
        'Category',
        'category',
        categoryOptions,
        'Select category…'
      )}
      {renderAutocomplete('Topic', 'topic', topicOptions, 'Select topic…')}

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
