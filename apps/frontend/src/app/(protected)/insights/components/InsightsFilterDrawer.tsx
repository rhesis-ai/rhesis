'use client';

import * as React from 'react';
import { FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import {
  behaviorIdsFromCheckedSelection,
  checkedBehaviorIdsFromFilter,
  InsightsBehaviorOption,
} from '../utils/insights-filter-utils';
import InsightsBehaviorFilterSection from './InsightsBehaviorFilterSection';

export interface InsightsDrawerFilters {
  endpointId: string;
  behaviorIds: string[];
}

export const EMPTY_INSIGHTS_DRAWER_FILTERS: InsightsDrawerFilters = {
  endpointId: '',
  behaviorIds: [],
};

export function hasActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): boolean {
  return f.endpointId !== '' || f.behaviorIds.length > 0;
}

export function countActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): number {
  let count = f.endpointId !== '' ? 1 : 0;
  if (f.behaviorIds.length > 0) {
    count += 1;
  }
  return count;
}

const selectSx = {
  borderRadius: BORDER_RADIUS.sm,
  fontSize: 14,
  '& .MuiOutlinedInput-notchedOutline': {
    borderRadius: BORDER_RADIUS.sm,
  },
};

interface InsightsFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: InsightsDrawerFilters;
  projectEndpoints: Endpoint[];
  endpointsLoading: boolean;
  behaviorOptions: InsightsBehaviorOption[];
  onApply: (filters: InsightsDrawerFilters) => void;
}

export default function InsightsFilterDrawer({
  open,
  onClose,
  filters,
  projectEndpoints,
  endpointsLoading,
  behaviorOptions,
  onApply,
}: InsightsFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_INSIGHTS_DRAWER_FILTERS,
    onApply,
    onClose
  );

  const allBehaviorIds = React.useMemo(
    () => behaviorOptions.map(option => option.id),
    [behaviorOptions]
  );

  const checkedBehaviorIds = React.useMemo(
    () => checkedBehaviorIdsFromFilter(allBehaviorIds, draft.behaviorIds),
    [allBehaviorIds, draft.behaviorIds]
  );

  const handleCheckedBehaviorIdsChange = React.useCallback(
    (checkedIds: string[]) => {
      setDraft(prev => ({
        ...prev,
        behaviorIds: behaviorIdsFromCheckedSelection(
          allBehaviorIds,
          checkedIds
        ),
      }));
    },
    [allBehaviorIds, setDraft]
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Endpoint">
        <FormControl
          fullWidth
          size="small"
          disabled={endpointsLoading || projectEndpoints.length === 0}
        >
          <InputLabel id="insights-filter-endpoint-label">Endpoint</InputLabel>
          <Select
            labelId="insights-filter-endpoint-label"
            value={draft.endpointId || ''}
            label="Endpoint"
            onChange={e =>
              setDraft(prev => ({ ...prev, endpointId: e.target.value }))
            }
            sx={selectSx}
          >
            {projectEndpoints.map(endpoint => (
              <MenuItem key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>

      <InsightsBehaviorFilterSection
        options={behaviorOptions}
        checkedIds={checkedBehaviorIds}
        onCheckedIdsChange={handleCheckedBehaviorIdsChange}
      />
    </FilterDrawerShell>
  );
}
