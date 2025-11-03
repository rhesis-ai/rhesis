'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { AddIcon, DeleteIcon } from '@/components/icons';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Task } from '@/utils/api-client/interfaces/task';
import { Typography, Box, Alert, Chip, Button, Avatar } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTaskFiltersToOData } from '@/utils/odata-filter';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface TasksGridProps {
  sessionToken: string;
  onRefresh?: () => void;
}

export default function TasksGrid({ sessionToken, onRefresh }: TasksGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Component state
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

  // Data fetching function
  const fetchTasks = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const tasksClient = clientFactory.getTasksClient();

      // Convert filter model to OData filter
      const oDataFilter = combineTaskFiltersToOData(filterModel);

      const response = await tasksClient.getTasks({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        $filter: oDataFilter,
      });

      setTasks(response.data);
      setTotalCount(response.totalCount || 0);

      setError(null);
    } catch (error) {
      setError('Failed to load tasks');
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [
    sessionToken,
    paginationModel.page,
    paginationModel.pageSize,
    filterModel,
  ]);

  // Initial data fetch
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Delete task
  const deleteTask = useCallback(
    async (taskId: string) => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const tasksClient = clientFactory.getTasksClient();

        await tasksClient.deleteTask(taskId);

        // Remove from local state
        setTasks(prev => prev.filter(task => task.id !== taskId));
        setSelectedRows(prev => prev.filter(id => id !== taskId));
        // Update total count
        setTotalCount(prev => Math.max(0, prev - 1));

        notifications.show('Task deleted successfully', {
          severity: 'success',
        });
        onRefresh?.();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to delete task';
        notifications.show(errorMessage, { severity: 'error' });

        // Refresh data to ensure consistency after delete failure
        fetchTasks();
      }
    },
    [sessionToken, onRefresh, fetchTasks]
  );

  // Delete selected tasks
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
    } catch (err) {
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [selectedRows, deleteTask]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
  }, []);

  // Handle row click
  const handleRowClick = useCallback(
    (params: any) => {
      router.push(`/tasks/${params.id}`);
    },
    [router]
  );

  // Get action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];

    buttons.push({
      label: 'Create Task',
      onClick: () => router.push('/tasks/create'),
      icon: <AddIcon />,
      variant: 'contained' as const,
      color: 'primary' as const,
    });

    if (selectedRows.length > 0) {
      buttons.push({
        label: `Delete (${selectedRows.length})`,
        onClick: handleDeleteSelected,
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
      });
    }

    return buttons;
  }, [selectedRows.length, handleDeleteSelected, router]);

  // Handle pagination change
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Handle filter change
  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    // Reset to first page when filters change
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  // Column definitions
  const columns: GridColDef[] = React.useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        width: 300,
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
        renderCell: params => {
          const getStatusColor = (status?: string) => {
            switch (status) {
              case 'Open':
                return 'warning';
              case 'In Progress':
                return 'primary';
              case 'Completed':
                return 'success';
              case 'Cancelled':
                return 'error';
              default:
                return 'default';
            }
          };

          return (
            <Chip
              label={params.row.status?.name || 'Unknown'}
              color={getStatusColor(params.row.status?.name) as any}
              size="small"
            />
          );
        },
      },
      {
        field: 'assignee',
        headerName: 'Assignee',
        width: 150,
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
    <Box>
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
        disablePaperWrapper={true}
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
    </Box>
  );
}
