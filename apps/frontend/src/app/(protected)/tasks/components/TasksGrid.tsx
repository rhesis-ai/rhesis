'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useContext,
  useMemo,
  useRef,
} from 'react';
import { DeleteIcon } from '@/components/icons';
import {
  GridColDef,
  GridRowSelectionModel,
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
import {
  Typography,
  Box,
  Alert,
  Avatar,
  Button,
  ButtonGroup,
} from '@mui/material';
import { FilterButton } from '@/components/common/FilterButton';
import GridBadge from '@/components/common/GridBadge';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTaskFiltersToOData } from '@/utils/odata-filter';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import { SearchPill } from '@/components/common/SearchPill';
import { BORDER_RADIUS, GREYSCALE } from '@/styles/theme';
import TaskFilterDrawer, {
  type TaskFilters,
  EMPTY_TASK_FILTERS,
  hasActiveTaskFilters,
} from './TaskFilterDrawer';

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
}

const TasksToolbarContext = React.createContext<TasksToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
});

function TasksUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
  } = useContext(TasksToolbarContext);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        minHeight: 52,
      }}
    >
      <FilterButton
        onClick={openFilterDrawer}
        hasActiveFilters={hasActiveDrawerFilters}
      />

      <SearchPill
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search tasks…"
        width={240}
      />

      <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <ButtonGroup
          variant="outlined"
          size="small"
          sx={{
            '& .MuiButtonGroup-grouped': {
              borderRadius: 0,
              '&:first-of-type': {
                borderTopLeftRadius: BORDER_RADIUS.pill,
                borderBottomLeftRadius: BORDER_RADIUS.pill,
              },
              '&:last-of-type': {
                borderTopRightRadius: BORDER_RADIUS.pill,
                borderBottomRightRadius: BORDER_RADIUS.pill,
              },
              borderColor: theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.border
                  : GREYSCALE.dark.border,
            },
          }}
        >
          {STATUS_PILL_TABS.map(tab => (
            <Button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              sx={{
                px: 2,
                py: 0.5,
                fontWeight: statusFilter === tab.value ? 600 : 400,
                bgcolor:
                  statusFilter === tab.value ? 'primary.dark' : 'transparent',
                color:
                  statusFilter === tab.value
                    ? '#fff'
                    : theme =>
                        theme.palette.mode === 'light'
                          ? GREYSCALE.light.body
                          : GREYSCALE.dark.body,
                '&:hover': {
                  bgcolor:
                    statusFilter === tab.value
                      ? 'primary.dark'
                      : theme =>
                          theme.palette.mode === 'light'
                            ? GREYSCALE.light.surface1
                            : GREYSCALE.dark.surface1,
                },
              }}
            >
              {tab.label}
            </Button>
          ))}
        </ButtonGroup>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <GridToolbarColumnsButton />
        <GridToolbarDensitySelector />
        <GridToolbarExport />
      </Box>
    </Box>
  );
}

export default function TasksGrid({
  sessionToken,
  refreshKey,
  onRefresh,
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
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
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
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<TaskFilters>(EMPTY_TASK_FILTERS);

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

  const deleteTask = useCallback(
    async (taskId: string) => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const tasksClient = clientFactory.getTasksClient();

        await tasksClient.deleteTask(taskId);

        setTasks(prev => prev.filter(task => task.id !== taskId));
        setSelectedRows(prev => prev.filter(id => id !== taskId));
        setTotalCount(prev => Math.max(0, prev - 1));

        notifications.show('Task deleted successfully', {
          severity: 'success',
        });
        onRefresh?.();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to delete task';
        notifications.show(errorMessage, { severity: 'error' });
        fetchTasks();
      }
    },
    [sessionToken, onRefresh, fetchTasks, notifications]
  );

  const handleDeleteSelected = useCallback(() => {
    if (selectedRows.length === 0) return;
    setDeleteModalOpen(true);
  }, [selectedRows]);

  const handleDeleteConfirm = useCallback(async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      await Promise.all(selectedRows.map(id => deleteTask(id as string)));
      setSelectedRows([]);
    } catch {
      // Individual delete errors are handled in deleteTask
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [selectedRows, deleteTask]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
  }, []);

  const handleRowClick = useCallback(
    (params: GridRowParams) => {
      router.push(`/tasks/${params.id}`);
    },
    [router]
  );

  const getActionButtons = useCallback(() => {
    if (selectedRows.length === 0) return [];

    return [
      {
        label: `Delete (${selectedRows.length})`,
        onClick: handleDeleteSelected,
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
      },
    ];
  }, [selectedRows.length, handleDeleteSelected]);

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

  const columns: GridColDef[] = useMemo(
    () => [
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
    ],
    []
  );

  return (
    <TasksToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        statusFilter,
        setStatusFilter,
        openFilterDrawer: () => setFilterDrawerOpen(true),
        hasActiveDrawerFilters: hasActiveTaskFilters(drawerFilters),
      }}
    >
      <Box sx={{ position: 'relative' }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {selectedRows.length > 0 && (
          <Box
            sx={{
              px: 2,
              py: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              borderBottom: theme =>
                `1px solid ${
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border
                }`,
            }}
          >
            <Typography variant="subtitle1" color="primary">
              {selectedRows.length} selected
            </Typography>
          </Box>
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
          actionButtons={getActionButtons()}
          checkboxSelection
          disableRowSelectionOnClick
          onRowSelectionModelChange={setSelectedRows}
          rowSelectionModel={selectedRows}
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
          title="Delete Tasks"
          message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'task' : 'tasks'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
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
  );
}
