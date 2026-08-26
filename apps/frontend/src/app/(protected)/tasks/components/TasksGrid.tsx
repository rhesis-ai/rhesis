'use client';

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useContext,
  useMemo,
} from 'react';
import {
  GridColDef,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Task } from '@/utils/api-client/interfaces/task';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { Typography, Box, Alert, Avatar, Paper } from '@mui/material';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import SelectionModeToggle from '@/components/common/SelectionModeToggle';
import GridBadge from '@/components/common/GridBadge';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useList } from '@/hooks/useList';
import { tasksList } from './list';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import TaskFilterDrawer, {
  type TaskFilters,
  EMPTY_TASK_FILTERS,
  hasActiveTaskFilters,
  countActiveTaskFilters,
} from './TaskFilterDrawer';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications as useJobNotifications } from '@/contexts/NotificationsContext';
import {
  HIGHLIGHTED_ROW_CLASS,
  NotificationSection,
} from '@/constants/notifications';
import {
  useBulkDelete,
  type BulkDeleteActionsState,
} from '@/hooks/useBulkDelete';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';

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
] as const;

interface TasksToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
  checkboxSelectionMode: boolean;
  setCheckboxSelectionMode: (v: boolean) => void;
}

const TasksToolbarContext = React.createContext<TasksToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
  checkboxSelectionMode: false,
  setCheckboxSelectionMode: () => {},
});

function TasksUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
    checkboxSelectionMode,
    setCheckboxSelectionMode,
  } = useContext(TasksToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tasks…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={[...STATUS_PILL_TABS]}
          activeValue={statusFilter}
          onChange={setStatusFilter}
        />
      }
      rightContent={
        <>
          <SelectionModeToggle
            checked={checkboxSelectionMode}
            onChange={setCheckboxSelectionMode}
            label="Select tasks"
          />
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

export default function TasksGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: TasksGridProps) {
  const router = useRouter();
  const { highlightedIds, clearHighlight } = useJobNotifications();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<TaskFilters>(EMPTY_TASK_FILTERS);
  const [errorDismissed, setErrorDismissed] = useState(false);

  // A pill click wins over the drawer's own status value (the pill is
  // applied after drawer filters).
  const effectiveStatus =
    statusFilter !== 'all' ? statusFilter : drawerFilters.status;

  const filters = useMemo(
    () => ({
      search: searchQuery,
      status: effectiveStatus,
      priority: drawerFilters.priority,
      assignee: drawerFilters.assignee,
    }),
    [
      searchQuery,
      effectiveStatus,
      drawerFilters.priority,
      drawerFilters.assignee,
    ]
  );

  const {
    data: tasks,
    totalCount,
    isLoading: loading,
    error: rawError,
    refresh,
    paginationModel,
    onPaginationModelChange: handlePaginationModelChange,
  } = useList(tasksList, {
    filters,
    initialData,
    initialTotalCount,
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  const {
    checkboxSelectionMode,
    setCheckboxSelectionMode,
    selectedRows,
    handleSelectionChange,
    pendingDeleteId,
    deleteModalOpen,
    isDeleting,
    requestDelete,
    confirmDelete,
    cancelDelete,
  } = useBulkDelete({
    bulkDeleteFn: (ids: string[]) =>
      new ApiClientFactory().getTasksClient().bulkDeleteTasks(ids),
    onSuccess: refresh,
    itemLabelSingular: 'task',
    itemLabelPlural: 'tasks',
    getSkippedCount: response => response.forbidden_ids.length,
    skippedReason: 'not yours to delete',
    onBulkActionsChange,
  });

  const isFirstRefreshTrigger = useRef(true);
  useEffect(() => {
    if (isFirstRefreshTrigger.current) {
      isFirstRefreshTrigger.current = false;
      return;
    }
    refresh();
    // Only refreshTrigger (bumped by the page after a create) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      clearHighlight(NotificationSection.TASKS, String(params.id));
      router.push(`/tasks/${params.id}`);
    },
    [router, clearHighlight]
  );

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => router.push(`/tasks/${id}`),
      canEdit: row => can(row as unknown as Task, Capability.Task.UPDATE),
      onDelete: id => requestDelete(id),
      canDelete: row => can(row as unknown as Task, Capability.Task.DELETE),
    });
    return [
      {
        field: 'title',
        headerName: 'Title',
        width: 300,
        minWidth: 150,
        resizable: true,
        renderCell: params => (
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            {params.row.title}
          </Typography>
        ),
      },
      {
        field: 'description',
        headerName: 'Description',
        width: 400,
        minWidth: 150,
        resizable: true,
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
        resizable: true,
        renderCell: params => (
          <GridBadge label={params.row.status?.name || 'Unknown'} />
        ),
      },
      {
        field: 'assignee',
        headerName: 'Assignee',
        width: 150,
        minWidth: 120,
        resizable: true,
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
      actionsCol,
    ];
  }, [router, requestDelete]);

  const filtersActive = !!searchQuery || hasActiveTaskFilters(drawerFilters);

  return (
    <GridStateGate
      data={loading ? null : {}}
      error={error}
      isEmpty={totalCount === 0 && !filtersActive}
      emptyState={
        <EntityEmptyState
          icon={AssignmentOutlinedIcon}
          title="No tasks yet"
          description="Create tasks to track follow-ups, issues, and action items from tests and evaluations."
          actionLabel={canCreate ? 'Create task' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
    >
      <Paper sx={GRID_PAPER_SX}>
        <TasksToolbarContext.Provider
          value={{
            searchQuery,
            setSearchQuery,
            statusFilter,
            setStatusFilter,
            openFilterDrawer: () => setFilterDrawerOpen(true),
            hasActiveDrawerFilters: hasActiveTaskFilters(drawerFilters),
            activeFilterCount: countActiveTaskFilters(drawerFilters),
            checkboxSelectionMode,
            setCheckboxSelectionMode,
          }}
        >
          <Box sx={{ position: 'relative' }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
                {error}
              </Alert>
            )}

            <BaseDataGrid
              rows={tasks}
              columns={columns}
              loading={loading}
              getRowId={row => row.id}
              paginationModel={paginationModel}
              onPaginationModelChange={handlePaginationModelChange}
              disableRowSelectionOnClick={checkboxSelectionMode || undefined}
              onRowClick={checkboxSelectionMode ? undefined : handleRowClick}
              getRowClassName={params =>
                highlightedIds(NotificationSection.TASKS).includes(
                  String(params.id)
                )
                  ? HIGHLIGHTED_ROW_CLASS
                  : ''
              }
              serverSidePagination={true}
              totalRows={totalCount}
              pageSizeOptions={[10, 25, 50, 100]}
              serverSideFiltering={true}
              showToolbar={true}
              toolbarSlot={TasksUnifiedToolbar}
              disablePaperWrapper={true}
              persistState
              sx={{
                ...rowActionsHoverSx,
                '& .MuiDataGrid-row': {
                  cursor: 'pointer',
                },
              }}
              checkboxSelection={checkboxSelectionMode}
              isRowSelectable={(params: GridRowParams) =>
                can(params.row as unknown as Task, Capability.Task.DELETE)
              }
              rowSelectionModel={checkboxSelectionMode ? selectedRows : []}
              onRowSelectionModelChange={
                checkboxSelectionMode ? handleSelectionChange : undefined
              }
            />

            <DeleteModal
              open={deleteModalOpen}
              onClose={cancelDelete}
              onConfirm={confirmDelete}
              isLoading={isDeleting}
              title={pendingDeleteId ? 'Delete Task' : 'Delete Tasks'}
              message={
                pendingDeleteId
                  ? 'Are you sure you want to delete this task? This action cannot be undone.'
                  : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'task' : 'tasks'}? This action cannot be undone.`
              }
              itemType="tasks"
            />

            <TaskFilterDrawer
              open={filterDrawerOpen}
              onClose={() => setFilterDrawerOpen(false)}
              filters={drawerFilters}
              onApply={f => {
                setDrawerFilters(f);
                if (f.status) {
                  setStatusFilter(f.status);
                } else if (!drawerFilters.status) {
                  setStatusFilter('all');
                }
              }}
            />
          </Box>
        </TasksToolbarContext.Provider>
      </Paper>
    </GridStateGate>
  );
}
