'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useContext,
  useMemo,
  useRef,
} from 'react';
import {
  GridColDef,
  GridPaginationModel,
  GridFilterModel,
  GridRowParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Task } from '@/utils/api-client/interfaces/task';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { Typography, Box, Alert, Avatar } from '@mui/material';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import GridBadge from '@/components/common/GridBadge';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { combineTaskFiltersToOData } from '@/utils/odata-filter';
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
import { useNotifications } from '@/components/common/NotificationContext';

interface TasksGridProps {
  sessionToken: string;
  refreshKey?: number;
  onRefresh?: () => void;
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
}

const TasksToolbarContext = React.createContext<TasksToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
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
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

export default function TasksGrid({
  sessionToken,
  refreshKey,
  onRefresh: _onRefresh,
}: TasksGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<TaskFilters>(EMPTY_TASK_FILTERS);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const tasksClient = clientFactory.getTasksClient();

      const oDataFilter = combineTaskFiltersToOData(filterModel);

      const response = await tasksClient.getTasks({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        $filter: oDataFilter,
      });

      if (!isMounted.current) return;

      setTasks(response.data);
      setTotalCount(response.totalCount || 0);
      setError(null);
    } catch {
      if (!isMounted.current) return;
      setError('Failed to load tasks');
      setTasks([]);
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, [
    sessionToken,
    paginationModel.page,
    paginationModel.pageSize,
    filterModel,
  ]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  useEffect(() => {
    if (refreshKey !== undefined && refreshKey > 0) {
      fetchTasks();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => item.field !== 'quickFilter'
      );
      const items = searchQuery
        ? [
            ...otherItems,
            { field: 'quickFilter', operator: 'contains', value: searchQuery },
          ]
        : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery]);

  useEffect(() => {
    setFilterModel(prev => {
      const otherItems = prev.items.filter(item => item.field !== 'status');
      const items =
        statusFilter && statusFilter !== 'all'
          ? [
              ...otherItems,
              { field: 'status', operator: 'equals', value: statusFilter },
            ]
          : otherItems;
      return { ...prev, items };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [statusFilter]);

  useEffect(() => {
    const DRAWER_FIELDS = ['status', 'priority', 'assignee'];
    setFilterModel(prev => {
      const otherItems = prev.items.filter(
        item => !DRAWER_FIELDS.includes(item.field ?? '')
      );
      const drawerItems: typeof prev.items = [];
      if (drawerFilters.status) {
        drawerItems.push({
          field: 'status',
          operator: 'equals',
          value: drawerFilters.status,
        });
      }
      if (drawerFilters.priority) {
        drawerItems.push({
          field: 'priority',
          operator: 'equals',
          value: drawerFilters.priority,
        });
      }
      if (drawerFilters.assignee) {
        drawerItems.push({
          field: 'assignee',
          operator: 'equals',
          value: drawerFilters.assignee,
        });
      }
      return { ...prev, items: [...otherItems, ...drawerItems] };
    });
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [drawerFilters]);

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      router.push(`/tasks/${params.id}`);
    },
    [router]
  );

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  const handleRowDeleteAction = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteModalOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!pendingDeleteId) return;
    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const tasksClient = clientFactory.getTasksClient();
      await tasksClient.deleteTask(pendingDeleteId);
      notifications.show('Successfully deleted task', {
        severity: 'success',
        autoHideDuration: 4000,
      });
      setPendingDeleteId(null);
      fetchTasks();
    } catch {
      notifications.show('Failed to delete task', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [pendingDeleteId, sessionToken, notifications, fetchTasks]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
    setPendingDeleteId(null);
  }, []);

  const columns: GridColDef[] = useMemo(() => {
    const actionsCol = createRowActionsColumn({
      onEdit: id => router.push(`/tasks/${id}`),
      canEdit: row => can(row as unknown as Task, Capability.Task.UPDATE),
      onDelete: id => handleRowDeleteAction(id),
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
  }, [router, handleRowDeleteAction]);

  return (
    <TasksToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        statusFilter,
        setStatusFilter,
        openFilterDrawer: () => setFilterDrawerOpen(true),
        hasActiveDrawerFilters: hasActiveTaskFilters(drawerFilters),
        activeFilterCount: countActiveTaskFilters(drawerFilters),
      }}
    >
      <Box sx={{ position: 'relative' }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
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
          filterModel={filterModel}
          onFilterModelChange={handleFilterModelChange}
          disableRowSelectionOnClick
          onRowClick={handleRowClick}
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
        />

        <DeleteModal
          open={deleteModalOpen}
          onClose={handleDeleteCancel}
          onConfirm={handleDeleteConfirm}
          isLoading={isDeleting}
          title="Delete Task"
          message="Are you sure you want to delete this task? This action cannot be undone."
          itemType="task"
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
  );
}
