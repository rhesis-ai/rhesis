'use client';

import * as React from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { useStatuses } from '@/hooks/useLookups';

export interface EndpointFilters {
  connectionType: string;
  environment: string;
  status: string;
}

export const EMPTY_ENDPOINT_FILTERS: EndpointFilters = {
  connectionType: '',
  environment: '',
  status: '',
};

export function hasActiveEndpointFilters(f: EndpointFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

export function countActiveEndpointFilters(f: EndpointFilters): number {
  return Object.values(f).filter(v => v !== '').length;
}

const CONNECTION_TYPE_OPTIONS = [
  { label: 'REST', value: 'REST' },
  { label: 'WebSocket', value: 'WebSocket' },
  { label: 'gRPC', value: 'GRPC' },
  { label: 'SDK', value: 'SDK' },
] as const;

const ENVIRONMENT_OPTIONS = [
  { label: 'Production', value: 'production' },
  { label: 'Staging', value: 'staging' },
  { label: 'Development', value: 'development' },
  { label: 'Local', value: 'local' },
] as const;

const selectSx = {
  borderRadius: BORDER_RADIUS.sm,
  fontSize: 14,
  '& .MuiOutlinedInput-notchedOutline': {
    borderRadius: BORDER_RADIUS.sm,
  },
};

interface EndpointFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: EndpointFilters;
  onApply: (filters: EndpointFilters) => void;
}

export default function EndpointFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: EndpointFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_ENDPOINT_FILTERS,
    onApply,
    onClose
  );
  const { data: rawStatuses, isLoading: loadingOptions } = useStatuses(
    'General',
    open
  );
  const statuses = React.useMemo(
    () =>
      (rawStatuses ?? []).filter(
        (s, i, arr) => s?.name && arr.findIndex(x => x.name === s.name) === i
      ),
    [rawStatuses]
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      <FilterSection title="Connection Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {CONNECTION_TYPE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  connectionType:
                    prev.connectionType === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.connectionType === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Environment">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {ENVIRONMENT_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  environment: prev.environment === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.environment === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Status">
        <FormControl fullWidth size="small" disabled={loadingOptions}>
          <InputLabel id="endpoint-filter-status-label">Status</InputLabel>
          <Select
            labelId="endpoint-filter-status-label"
            label="Status"
            value={draft.status}
            onChange={e =>
              setDraft(prev => ({ ...prev, status: e.target.value }))
            }
            sx={selectSx}
          >
            <MenuItem value="">
              <em>All statuses</em>
            </MenuItem>
            {statuses.map(status => (
              <MenuItem key={status.id} value={status.name}>
                {status.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>
    </FilterDrawerShell>
  );
}
