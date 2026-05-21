'use client';

import * as React from 'react';
import { Box, TextField } from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';

export interface SourceFilters {
  sourceType: string;
  tag: string;
  creator: string;
}

export const EMPTY_SOURCE_FILTERS: SourceFilters = {
  sourceType: '',
  tag: '',
  creator: '',
};

export function hasActiveSourceFilters(f: SourceFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

const SOURCE_TYPE_OPTIONS = [
  { label: 'Document', value: 'Document' },
  { label: 'Tool', value: 'Tool' },
  { label: 'Website', value: 'Website' },
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

interface SourceFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: SourceFilters;
  onApply: (filters: SourceFilters) => void;
}

export default function SourceFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: SourceFilterDrawerProps) {
  const [draft, setDraft] = React.useState<SourceFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_SOURCE_FILTERS);

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
      title="Filter"
    >
      <FilterSection title="Source Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {SOURCE_TYPE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  sourceType: prev.sourceType === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.sourceType === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Creator">
        <TextField
          fullWidth
          placeholder="Filter by creator name…"
          value={draft.creator}
          onChange={e =>
            setDraft(prev => ({ ...prev, creator: e.target.value }))
          }
          sx={textFieldSx}
        />
      </FilterSection>

      <FilterSection title="Tag">
        <TextField
          fullWidth
          placeholder="Filter by tag name…"
          value={draft.tag}
          onChange={e => setDraft(prev => ({ ...prev, tag: e.target.value }))}
          sx={textFieldSx}
        />
      </FilterSection>
    </FilterDrawerShell>
  );
}
