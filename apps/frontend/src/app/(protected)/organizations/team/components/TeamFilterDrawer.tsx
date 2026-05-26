'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { EMPTY_TEAM_FILTERS, type TeamFilters } from '@/utils/odata-filter';

export { EMPTY_TEAM_FILTERS, type TeamFilters };
export { hasActiveTeamFilters } from '@/utils/odata-filter';

const MEMBER_STATUS_OPTIONS = [
  { label: 'Active', value: 'active' as const },
  { label: 'Invited', value: 'invited' as const },
];

const ACCOUNT_STATUS_OPTIONS = [
  { label: 'Active account', value: true as const },
  { label: 'Inactive account', value: false as const },
];

interface TeamFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TeamFilters;
  onApply: (filters: TeamFilters) => void;
}

export default function TeamFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TeamFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_TEAM_FILTERS,
    onApply,
    onClose
  );

  const textFieldSx = {
    '& .MuiOutlinedInput-root': {
      borderRadius: BORDER_RADIUS.sm,
      fontSize: 14,
    },
    '& .MuiOutlinedInput-input': {
      padding: '20px 14px',
    },
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Member status">
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {MEMBER_STATUS_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  memberStatus:
                    prev.memberStatus === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.memberStatus === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Account status">
        <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {ACCOUNT_STATUS_OPTIONS.map(opt => (
            <Box
              key={String(opt.value)}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  accountStatus:
                    prev.accountStatus === opt.value ? null : opt.value,
                }))
              }
              sx={filterChipSx(draft.accountStatus === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Email">
        <TextField
          fullWidth
          placeholder="Filter by email address…"
          value={draft.email}
          onChange={e => setDraft(prev => ({ ...prev, email: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>

      <FilterSection title="Name">
        <TextField
          fullWidth
          placeholder="Filter by display or given name…"
          value={draft.name}
          onChange={e => setDraft(prev => ({ ...prev, name: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
