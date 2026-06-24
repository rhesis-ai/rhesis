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

export interface InsightsDrawerFilters {
  endpointId: string;
}

export const EMPTY_INSIGHTS_DRAWER_FILTERS: InsightsDrawerFilters = {
  endpointId: '',
};

export function hasActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): boolean {
  return f.endpointId !== '';
}

export function countActiveInsightsDrawerFilters(
  f: InsightsDrawerFilters
): number {
  return f.endpointId !== '' ? 1 : 0;
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
  onApply: (filters: InsightsDrawerFilters) => void;
}

export default function InsightsFilterDrawer({
  open,
  onClose,
  filters,
  projectEndpoints,
  endpointsLoading,
  onApply,
}: InsightsFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_INSIGHTS_DRAWER_FILTERS,
    onApply,
    onClose
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
    </FilterDrawerShell>
  );
}
