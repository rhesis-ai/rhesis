'use client';

import React, { useCallback, useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import { Typography, Box, Avatar } from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { Task } from '@/utils/api-client/interfaces/task';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { NotificationSection } from '@/constants/notifications';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { tasksList } from './list';
import TaskFilterDrawer, {
  type TaskFilters,
  EMPTY_TASK_FILTERS,
  countActiveTaskFilters,
} from './TaskFilterDrawer';

interface TasksGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
  /** Bumped by the page after a create succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Task[];
  initialTotalCount?: number;
}

const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Open', value: 'Open' },
  { label: 'In Progress', value: 'In Progress' },
  { label: 'Completed', value: 'Completed' },
  { label: 'Cancelled', value: 'Cancelled' },
];

// A pill click wins over the drawer's own status value (the pill is applied
// after drawer filters).
function toFilters(state: EntityGridFilterState<TaskFilters>) {
  return {
    search: state.search,
    status: state.pill || state.drawer.status,
    priority: state.drawer.priority,
    assignee: state.drawer.assignee,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TaskFilters> = {
  empty: EMPTY_TASK_FILTERS,
  countActive: countActiveTaskFilters,
  render: props => (
    <TaskFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
  // Applying a status in the drawer syncs the pill; clearing it resets the
  // pill only when no drawer status was active before.
  pillFromApply: (applied, previous) =>
    applied.status ? applied.status : !previous.status ? '' : undefined,
};

export default function TasksGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: TasksGridProps) {
  const getRowUrl = useCallback((row: Task) => `/tasks/${row.id}`, []);

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        flex: 3,
        minWidth: 150,
        renderCell: params => (
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            {params.row.title}
          </Typography>
        ),
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 4,
        minWidth: 150,
        renderCell: params => (
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              maxWidth: '100%',
            }}
          >
            {params.row.description || '-'}
          </Typography>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        minWidth: 90,
        flex: 0,
        sortable: false,
        renderCell: params => (
          <GridBadge label={params.row.status?.name || 'Unknown'} />
        ),
      },
      {
        field: 'assignee',
        headerName: 'Assignee',
        flex: 1.5,
        minWidth: 120,
        sortable: false,
        renderCell: params => {
          if (!params.row.assignee?.name) {
            return null;
          }

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar
                src={params.row.assignee?.picture}
                alt={params.row.assignee?.name}
                sx={{
                  width: AVATAR_SIZES.SMALL,
                  height: AVATAR_SIZES.SMALL,
                  bgcolor: 'primary.main',
                }}
              >
                {params.row.assignee?.name?.charAt(0)}
              </Avatar>
              <Typography variant="body2">
                {params.row.assignee?.name}
              </Typography>
            </Box>
          );
        },
      },
    ],
    []
  );

  return (
    <EntityGrid<Task, typeof tasksList.filters, TaskFilters>
      descriptor={tasksList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          icon={AssignmentOutlinedIcon}
          title="No tasks yet"
          description="Create tasks to track follow-ups, issues, and action items from tests and evaluations."
          actionLabel={canCreate ? 'Create task' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      searchPlaceholder="Search tasks…"
      pills={{ tabs: STATUS_PILL_TABS }}
      drawer={drawerAdapter}
      selectionLabel="Select tasks"
      getRowUrl={getRowUrl}
      highlightSection={NotificationSection.TASKS}
      editAction={{ can: (row: Task) => can(row, Capability.Task.UPDATE) }}
      onBulkActionsChange={onBulkActionsChange}
      pageSizeOptions={[10, 25, 50, 100]}
      sx={{ '& .MuiDataGrid-row': { cursor: 'pointer' } }}
    />
  );
}
