'use client';

import * as React from 'react';
import { Autocomplete, Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { filterUniqueValidOptions } from '@/components/common/BaseDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { TEST_TYPES } from '@/constants/test-types';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ENTITY_TYPES } from '@/utils/api-client/config';

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

export function countActiveTestSetFilters(f: TestSetFilters): number {
  return Object.values(f).filter(v => v !== '').length;
}

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
  const [statusOptions, setStatusOptions] = React.useState<string[]>([]);
  const [creatorOptions, setCreatorOptions] = React.useState<string[]>([]);
  const [tagOptions, setTagOptions] = React.useState<string[]>([]);
  const [loadingOptions, setLoadingOptions] = React.useState(false);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  React.useEffect(() => {
    if (!open || !sessionToken) return;

    const loadOptions = async () => {
      setLoadingOptions(true);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const [statusesData, usersData, tagsData] = await Promise.all([
          apiFactory.getStatusClient().getStatuses({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: ENTITY_TYPES.testSet,
          }),
          apiFactory.getUsersClient().getUsers(),
          apiFactory.getTagsClient().getTags({
            sort_by: 'name',
            sort_order: 'asc',
          }),
        ]);

        setStatusOptions(
          filterUniqueValidOptions(statusesData).map(s => s.name)
        );
        setCreatorOptions(
          usersData.data
            .map(
              user =>
                user.name ||
                `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
                user.email
            )
            .filter(Boolean)
        );
        setTagOptions(tagsData.map(tag => tag.name).filter(Boolean));
      } catch {
        // Keep empty options on failure
      } finally {
        setLoadingOptions(false);
      }
    };

    loadOptions();
  }, [open, sessionToken]);

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
        value={draft[field]}
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
          {TEST_SET_TYPE_OPTIONS.map(opt => (
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
    </FilterDrawerShell>
  );
}
