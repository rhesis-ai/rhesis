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
import { TEST_TYPE_FILTER_OPTIONS } from '@/constants/test-types';
import { ENTITY_TYPES } from '@/utils/api-client/config';
import { useStatuses, useUsers, useTags } from '@/hooks/useLookups';
import ActivityPresenceFiltersSection from '@/components/common/ActivityPresenceFilters';
import {
  EMPTY_ACTIVITY_PRESENCE_FILTERS,
  countActivePresenceFilters,
  hasActivePresenceFilters,
  type ActivityPresenceFilters,
} from '@/components/common/presence-filter';

export interface TestSetFilters {
  /** test_set_type/type_value equals */
  testSetType: string;
  /** status/name contains */
  status: string;
  /** user/name contains */
  creator: string;
  /** tags/name contains */
  tag: string;
  tags: ActivityPresenceFilters['tags'];
  comments: ActivityPresenceFilters['comments'];
  tasks: ActivityPresenceFilters['tasks'];
}

export const EMPTY_TEST_SET_FILTERS: TestSetFilters = {
  testSetType: '',
  status: '',
  creator: '',
  tag: '',
  ...EMPTY_ACTIVITY_PRESENCE_FILTERS,
};

export function hasActiveTestSetFilters(f: TestSetFilters): boolean {
  return (
    f.testSetType !== '' ||
    f.status !== '' ||
    f.creator !== '' ||
    f.tag !== '' ||
    hasActivePresenceFilters(f)
  );
}

export function countActiveTestSetFilters(f: TestSetFilters): number {
  return (
    (f.testSetType !== '' ? 1 : 0) +
    (f.status !== '' ? 1 : 0) +
    (f.creator !== '' ? 1 : 0) +
    (f.tag !== '' ? 1 : 0) +
    countActivePresenceFilters(f)
  );
}

const textFieldSx = filterDrawerTextFieldSx;

interface TestSetFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestSetFilters;
  sessionToken?: string;
  onApply: (filters: TestSetFilters) => void;
}

export default function TestSetFilterDrawer({
  open,
  onClose,
  filters,
  sessionToken,
  onApply,
}: TestSetFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestSetFilters>(filters);
  const token = sessionToken ?? '';

  const { data: rawStatuses, isLoading: loadingStatuses } = useStatuses(
    token,
    ENTITY_TYPES.testSet,
    open
  );
  const { data: rawUsers, isLoading: loadingUsers } = useUsers(token, open);
  const { data: rawTags, isLoading: loadingTags } = useTags(token, open);
  const loadingOptions = loadingStatuses || loadingUsers || loadingTags;

  const statusOptions = React.useMemo(
    () => filterUniqueValidOptions(rawStatuses ?? []).map(s => s.name),
    [rawStatuses]
  );
  const creatorOptions = React.useMemo(
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

  const handleReset = () => setDraft(EMPTY_TEST_SET_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

  const renderAutocomplete = (
    title: string,
    field: keyof Pick<TestSetFilters, 'status' | 'creator' | 'tag'>,
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
      title="Filter"
    >
      <FilterSection title="Test Set Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TEST_TYPE_FILTER_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
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

      {renderAutocomplete('Status', 'status', statusOptions, 'Select status…')}
      {renderAutocomplete(
        'Creator',
        'creator',
        creatorOptions,
        'Select creator…'
      )}
      {renderAutocomplete('Tag', 'tag', tagOptions, 'Select tag…')}

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
