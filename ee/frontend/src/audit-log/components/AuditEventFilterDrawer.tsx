'use client';

import * as React from 'react';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import { useQuery } from '@tanstack/react-query';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  filterDrawerSelectSx,
  filterDrawerTextFieldSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { useUsers } from '@/hooks/useLookups';
import { AuditLogClient } from '../api/audit-log-client';
import {
  EMPTY_AUDIT_EVENT_FILTERS,
  auditLogQueryKeys,
  type AuditEventFilters,
} from '../filters';
import {
  CHANNEL_LABELS,
  OUTCOME_LABELS,
  actionArea,
  actionLabel,
} from '../labels';
import type { AuditAction } from '../types';

const OTHER_GROUP = 'Other';

interface ActionOption {
  action: string;
  label: string;
  group: string;
}

function toOptions(actions: AuditAction[]): ActionOption[] {
  return actions
    .map(a => ({
      action: a.action,
      label: actionLabel(a.action),
      group: actionArea(a.action)?.label ?? OTHER_GROUP,
    }))
    .sort(
      (a, b) => a.group.localeCompare(b.group) || a.label.localeCompare(b.label)
    );
}

function ChipRow<K extends string>({
  labels,
  value,
  onChange,
}: {
  labels: Record<K, string>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      {(Object.entries(labels) as [K, string][]).map(([key, label]) => (
        <Box
          key={key}
          component="button"
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(value === key ? '' : key)}
          sx={filterChipSx(value === key)}
        >
          {label}
        </Box>
      ))}
    </Box>
  );
}

interface AuditEventFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: AuditEventFilters;
  onApply: (filters: AuditEventFilters) => void;
}

export default function AuditEventFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: AuditEventFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_AUDIT_EVENT_FILTERS,
    onApply,
    onClose
  );

  // Both lists only feed this drawer, so they load when it opens.
  const { data: actions, isLoading: loadingActions } = useQuery({
    queryKey: auditLogQueryKeys.actions(),
    queryFn: () => new AuditLogClient().listActions(),
    enabled: open,
    staleTime: Infinity,
  });
  const actionOptions = React.useMemo(
    () => toOptions(actions ?? []),
    [actions]
  );
  const selectedAction =
    actionOptions.find(o => o.action === draft.action) ?? null;

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
      <FilterSection title="Action">
        <Autocomplete
          size="small"
          options={actionOptions}
          loading={loadingActions}
          value={selectedAction}
          groupBy={option => option.group}
          getOptionLabel={option => option.label}
          isOptionEqualToValue={(a, b) => a.action === b.action}
          onChange={(_event, option) =>
            setDraft(prev => ({ ...prev, action: option?.action ?? '' }))
          }
          renderInput={params => (
            <TextField
              {...params}
              label="Action"
              placeholder="Any action"
              sx={filterDrawerTextFieldSx}
            />
          )}
        />
      </FilterSection>

      <FilterSection title="Actor">
        <FormControl fullWidth size="small" disabled={loadingUsers}>
          <InputLabel id="audit-filter-actor-label">Actor</InputLabel>
          <Select
            labelId="audit-filter-actor-label"
            value={draft.actor}
            label="Actor"
            onChange={e =>
              setDraft(prev => ({ ...prev, actor: e.target.value }))
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

      <FilterSection title="Result">
        <ChipRow
          labels={OUTCOME_LABELS}
          value={draft.outcome}
          onChange={outcome => setDraft(prev => ({ ...prev, outcome }))}
        />
      </FilterSection>

      <FilterSection title="Source">
        <ChipRow
          labels={CHANNEL_LABELS}
          value={draft.channel}
          onChange={channel => setDraft(prev => ({ ...prev, channel }))}
        />
      </FilterSection>

      <FilterSection title="Date">
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            label="From"
            type="date"
            size="small"
            fullWidth
            value={draft.from}
            onChange={e =>
              setDraft(prev => ({ ...prev, from: e.target.value }))
            }
            slotProps={{ inputLabel: { shrink: true } }}
            sx={filterDrawerTextFieldSx}
          />
          <TextField
            label="To"
            type="date"
            size="small"
            fullWidth
            value={draft.to}
            onChange={e => setDraft(prev => ({ ...prev, to: e.target.value }))}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={filterDrawerTextFieldSx}
          />
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
