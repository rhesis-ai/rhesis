'use client';

import * as React from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';

export interface ModelFilters {
  providers: string[];
  status: string;
}

export const EMPTY_MODEL_FILTERS: ModelFilters = {
  providers: [],
  status: '',
};

export function hasActiveModelFilters(f: ModelFilters): boolean {
  return f.providers.length > 0 || f.status !== '';
}

export function countActiveModelFilters(f: ModelFilters): number {
  return f.providers.length + (f.status !== '' ? 1 : 0);
}

const selectSx = {
  borderRadius: BORDER_RADIUS.sm,
  fontSize: 14,
  '& .MuiOutlinedInput-notchedOutline': {
    borderRadius: BORDER_RADIUS.sm,
  },
};

interface ModelFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: ModelFilters;
  providerOptions: TypeLookup[];
  statusOptions: string[];
  onApply: (filters: ModelFilters) => void;
}

export default function ModelFilterDrawer({
  open,
  onClose,
  filters,
  providerOptions,
  statusOptions,
  onApply,
}: ModelFilterDrawerProps) {
  const [draft, setDraft] = React.useState<ModelFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const toggleProvider = (provider: string) => {
    setDraft(prev => ({
      ...prev,
      providers: prev.providers.includes(provider)
        ? prev.providers.filter(p => p !== provider)
        : [...prev.providers, provider],
    }));
  };

  const handleReset = () => setDraft(EMPTY_MODEL_FILTERS);

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
      {providerOptions.length > 0 && (
        <FilterSection title="Provider">
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {providerOptions.map(provider => (
              <Box
                key={provider.id}
                component="button"
                type="button"
                onClick={() => toggleProvider(provider.type_value)}
                sx={filterChipSx(draft.providers.includes(provider.type_value))}
              >
                {provider.type_value}
              </Box>
            ))}
          </Box>
        </FilterSection>
      )}

      {statusOptions.length > 0 && (
        <FilterSection title="Status">
          <FormControl fullWidth size="small">
            <InputLabel id="model-filter-status-label">Status</InputLabel>
            <Select
              labelId="model-filter-status-label"
              value={draft.status}
              label="Status"
              onChange={e =>
                setDraft(prev => ({ ...prev, status: e.target.value }))
              }
              sx={selectSx}
            >
              <MenuItem value="">All statuses</MenuItem>
              {statusOptions.map(status => (
                <MenuItem key={status} value={status}>
                  {status}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </FilterSection>
      )}
    </FilterDrawerShell>
  );
}
