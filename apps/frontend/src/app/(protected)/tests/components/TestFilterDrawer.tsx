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
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ENTITY_TYPES } from '@/utils/api-client/config';

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

export function countActiveTestFilters(f: TestFilters): number {
  return Object.values(f).filter(v => v !== '').length;
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
  sessionToken?: string;
  onApply: (filters: TestFilters) => void;
}

export default function TestFilterDrawer({
  open,
  onClose,
  filters,
  sessionToken,
  onApply,
}: TestFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestFilters>(filters);
  const [statusOptions, setStatusOptions] = React.useState<string[]>([]);
  const [behaviorOptions, setBehaviorOptions] = React.useState<string[]>([]);
  const [categoryOptions, setCategoryOptions] = React.useState<string[]>([]);
  const [topicOptions, setTopicOptions] = React.useState<string[]>([]);
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
        const [statusesData, behaviorsData, categoriesData, topicsData] =
          await Promise.all([
            apiFactory.getStatusClient().getStatuses({
              sort_by: 'name',
              sort_order: 'asc',
              entity_type: ENTITY_TYPES.test,
            }),
            apiFactory.getBehaviorClient().getBehaviors({
              sort_by: 'name',
              sort_order: 'asc',
            }),
            apiFactory.getCategoryClient().getCategories({
              sort_by: 'name',
              sort_order: 'asc',
              entity_type: 'Test',
            }),
            apiFactory.getTopicClient().getTopics({
              sort_by: 'name',
              sort_order: 'asc',
              entity_type: 'Test',
            }),
          ]);

        setStatusOptions(
          filterUniqueValidOptions(statusesData).map(s => s.name)
        );
        setBehaviorOptions(
          filterUniqueValidOptions(behaviorsData).map(b => b.name)
        );
        setCategoryOptions(
          filterUniqueValidOptions(categoriesData).map(c => c.name)
        );
        setTopicOptions(filterUniqueValidOptions(topicsData).map(t => t.name));
      } catch {
        // Keep empty options on failure
      } finally {
        setLoadingOptions(false);
      }
    };

    loadOptions();
  }, [open, sessionToken]);

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
    >
      <FilterSection title="Test Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {TEST_TYPE_OPTIONS.map(opt => (
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
    </FilterDrawerShell>
  );
}
