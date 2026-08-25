'use client';

import * as React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerSelectSx,
  filterDrawerTextFieldSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { useUsers } from '@/hooks/useLookups';
import { EMPTY_JOB_FILTERS, type JobFilters } from '@/utils/odata-filter';
import { JOB_STATUS_OPTIONS, JOB_TYPE_OPTIONS } from '@/constants/jobs';

interface JobFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: JobFilters;
  onApply: (filters: JobFilters) => void;
}

export default function JobFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: JobFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_JOB_FILTERS,
    onApply,
    onClose
  );

  // Only fetched while the drawer is open: the list is only needed to populate
  // this one dropdown.
  const { data: rawUsers, isLoading: loadingUsers } = useUsers(open);
  const users = React.useMemo(
    () => (rawUsers ?? []).filter(user => user.id && user.name),
    [rawUsers]
  );

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      <FilterSection title="Status">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {JOB_STATUS_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  status: prev.status === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.status === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Type">
        <FormControl fullWidth size="small">
          <InputLabel id="job-filter-type-label">Type</InputLabel>
          <Select
            labelId="job-filter-type-label"
            value={draft.jobType}
            label="Type"
            onChange={e =>
              setDraft(prev => ({ ...prev, jobType: e.target.value }))
            }
            sx={filterDrawerSelectSx}
          >
            <MenuItem value="">All types</MenuItem>
            {JOB_TYPE_OPTIONS.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>

      <FilterSection title="Triggered by">
        <FormControl fullWidth size="small" disabled={loadingUsers}>
          <InputLabel id="job-filter-user-label">User</InputLabel>
          <Select
            labelId="job-filter-user-label"
            value={draft.triggeredBy}
            label="User"
            onChange={e =>
              setDraft(prev => ({ ...prev, triggeredBy: e.target.value }))
            }
            sx={filterDrawerSelectSx}
          >
            <MenuItem value="">Anyone</MenuItem>
            {users.map(user => (
              <MenuItem key={user.id} value={user.id}>
                {user.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>

      <FilterSection title="Created">
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            label="From"
            type="date"
            size="small"
            fullWidth
            value={draft.createdFrom}
            onChange={e =>
              setDraft(prev => ({ ...prev, createdFrom: e.target.value }))
            }
            InputLabelProps={{ shrink: true }}
            sx={filterDrawerTextFieldSx}
          />
          <TextField
            label="To"
            type="date"
            size="small"
            fullWidth
            value={draft.createdTo}
            onChange={e =>
              setDraft(prev => ({ ...prev, createdTo: e.target.value }))
            }
            InputLabelProps={{ shrink: true }}
            sx={filterDrawerTextFieldSx}
          />
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
