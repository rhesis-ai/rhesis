'use client';

import * as React from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { useSession } from 'next-auth/react';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import type { TaskStatus } from '@/types/tasks';
import { getPriorities } from '@/utils/task-lookup';
import type { Priority } from '@/utils/api-client/interfaces/task';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';

export interface TaskFilters {
  status: string;
  priority: string;
  assignee: string;
}

export const EMPTY_TASK_FILTERS: TaskFilters = {
  status: '',
  priority: '',
  assignee: '',
};

export function hasActiveTaskFilters(f: TaskFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

export function countActiveTaskFilters(f: TaskFilters): number {
  return Object.values(f).filter(v => v !== '').length;
}

const STATUS_OPTIONS: { label: string; value: TaskStatus }[] = [
  { label: 'Open', value: 'Open' },
  { label: 'In Progress', value: 'In Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'Cancelled', value: 'Cancelled' },
];

const selectSx = {
  borderRadius: BORDER_RADIUS.sm,
  fontSize: 14,
  '& .MuiOutlinedInput-notchedOutline': {
    borderRadius: BORDER_RADIUS.sm,
  },
};

interface TaskFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TaskFilters;
  onApply: (filters: TaskFilters) => void;
}

export default function TaskFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TaskFilterDrawerProps) {
  const { data: session } = useSession();
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_TASK_FILTERS,
    onApply,
    onClose
  );
  const [priorities, setPriorities] = React.useState<Priority[]>([]);
  const [users, setUsers] = React.useState<User[]>([]);
  const [loadingOptions, setLoadingOptions] = React.useState(false);

  React.useEffect(() => {
    const sessionToken = session?.session_token;
    if (!open || !sessionToken) return;

    const loadOptions = async () => {
      setLoadingOptions(true);
      try {
        const [fetchedPriorities, fetchedUsers] = await Promise.all([
          getPriorities(sessionToken),
          (async () => {
            const clientFactory = new ApiClientFactory(sessionToken);
            const usersClient = clientFactory.getUsersClient();
            const response = await usersClient.getUsers();
            return response.data.filter(user => user.id && user.name);
          })(),
        ]);
        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);
      } catch {
        setPriorities([]);
        setUsers([]);
      } finally {
        setLoadingOptions(false);
      }
    };

    loadOptions();
  }, [open, session?.session_token]);

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
          {STATUS_OPTIONS.map(opt => (
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

      <FilterSection title="Priority">
        <FormControl fullWidth size="small" disabled={loadingOptions}>
          <InputLabel id="task-filter-priority-label">Priority</InputLabel>
          <Select
            labelId="task-filter-priority-label"
            value={draft.priority}
            label="Priority"
            onChange={e =>
              setDraft(prev => ({ ...prev, priority: e.target.value }))
            }
            sx={selectSx}
          >
            <MenuItem value="">All priorities</MenuItem>
            {priorities.map(priority => (
              <MenuItem
                key={priority.id}
                value={priority.type_value || priority.id}
              >
                {priority.type_value || priority.id}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>

      <FilterSection title="Assignee">
        <FormControl fullWidth size="small" disabled={loadingOptions}>
          <InputLabel id="task-filter-assignee-label">Assignee</InputLabel>
          <Select
            labelId="task-filter-assignee-label"
            value={draft.assignee}
            label="Assignee"
            onChange={e =>
              setDraft(prev => ({ ...prev, assignee: e.target.value }))
            }
            sx={selectSx}
          >
            <MenuItem value="">All assignees</MenuItem>
            {users.map(user => (
              <MenuItem key={user.id} value={user.name}>
                {user.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>
    </FilterDrawerShell>
  );
}
