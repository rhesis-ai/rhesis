'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';

// ── Filter state ───────────────────────────────────────────────────────────────

export type TokenStatusFilter = 'all' | 'active' | 'expired';
export type TokenUsageFilter = 'all' | 'used' | 'never_used';

export interface TokenFilters {
  status: TokenStatusFilter;
  usage: TokenUsageFilter;
}

export const EMPTY_TOKEN_FILTERS: TokenFilters = {
  status: 'all',
  usage: 'all',
};

export function hasActiveTokenFilters(f: TokenFilters): boolean {
  return f.status !== 'all' || f.usage !== 'all';
}

// ── Constants ──────────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { label: string; value: TokenStatusFilter }[] = [
  { label: 'Active', value: 'active' },
  { label: 'Expired', value: 'expired' },
];

const USAGE_OPTIONS: { label: string; value: TokenUsageFilter }[] = [
  { label: 'Used', value: 'used' },
  { label: 'Never used', value: 'never_used' },
];

// ── Component ──────────────────────────────────────────────────────────────────

interface TokenFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TokenFilters;
  onApply: (filters: TokenFilters) => void;
}

export default function TokenFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TokenFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TokenFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TOKEN_FILTERS);

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
      {/* Status */}
      <FilterSection title="Status">
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {STATUS_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  status: prev.status === opt.value ? 'all' : opt.value,
                }))
              }
              sx={filterChipSx(draft.status === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      {/* Usage */}
      <FilterSection title="Usage">
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {USAGE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  usage: prev.usage === opt.value ? 'all' : opt.value,
                }))
              }
              sx={filterChipSx(draft.usage === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
