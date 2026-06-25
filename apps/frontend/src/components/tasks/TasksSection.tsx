'use client';

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Chip, Avatar } from '@mui/material';
import { AddIcon } from '@/components/icons';
import TasksIcon from '@/components/TasksIcon';
import { Task, EntityType } from '@/types/tasks';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { SectionCard } from '@/components/common/SectionCard';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
} from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { TaskErrorBoundary } from './TaskErrorBoundary';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface TasksSectionProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  onCreateTask: (taskData: Record<string, unknown>) => Promise<void>;
  onEditTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => Promise<void>;
  /** Opens the in-context task creation drawer */
  onOpenCreateDrawer?: (commentId?: string) => void;
  currentUserId: string;
  currentUserName: string;
  /** Bump after create/delete so the list refetches. */
  refreshKey?: number;
}

export function TasksSection({
  entityType,
  entityId,
  sessionToken,
  onCreateTask: _onCreateTask,
  onEditTask: _onEditTask,
  onDeleteTask,
  onOpenCreateDrawer,
  currentUserId: _currentUserId,
  currentUserName: _currentUserName,
  refreshKey = 0,
}: TasksSectionProps) {
  const router = useRouter();
  const { show: showNotification } = useNotifications();

  // Component state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  // Use a ref for the notification function to avoid including it
  // as an effect dependency, which could cause re-fetch loops.
  const showNotificationRef = React.useRef(showNotification);
  React.useEffect(() => {
    showNotificationRef.current = showNotification;
  }, [showNotification]);

  // Handle pagination changes
  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Extract primitive values to use as stable dependencies
  const currentPage = paginationModel.page;
  const currentPageSize = paginationModel.pageSize;

  // Fetch tasks - using a simpler, more robust pattern
  React.useEffect(() => {
    // Don't even create the controller if we're missing required props
    if (!entityType || !entityId || !sessionToken) {
      setLoading(false); // Important: ensure loading is false if we can't fetch
      return;
    }

    const abortController = new AbortController();

    const fetchTasks = async () => {
      setLoading(true);
      setError(null);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const tasksClient = clientFactory.getTasksClient();

        const skip = currentPage * currentPageSize;
        const filter = `entity_type eq '${entityType}' and entity_id eq ${entityId}`;

        const response = await tasksClient.getTasks({
          skip,
          limit: currentPageSize,
          sort_by: 'created_at',
          sort_order: 'desc',
          $filter: filter,
        });

        // Only update state if not aborted
        if (!abortController.signal.aborted) {
          setTasks(response.data);
          setTotalCount(response.totalCount);
          setLoading(false);
        }
      } catch (err) {
        // Only update state if not aborted
        if (!abortController.signal.aborted) {
          const errorMessage =
            err instanceof Error ? err.message : 'Failed to fetch tasks';
          setError(errorMessage);
          showNotificationRef.current(errorMessage, { severity: 'error' });
          setLoading(false);
        }
      }
    };

    fetchTasks();

    return () => {
      abortController.abort();
    };
  }, [
    currentPage,
    currentPageSize,
    entityType,
    entityId,
    sessionToken,
    refreshKey,
  ]);

  const _handleDeleteTask = async (taskId: string) => {
    if (onDeleteTask) {
      try {
        await onDeleteTask(taskId);
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
    }
  };

  const handleRowClick = (params: GridRowParams) => {
    try {
      router.push(`/tasks/${params.id}`);
    } catch (error) {
      console.error('Failed to navigate to task:', error);
    }
  };

  const handleCreateTask = () => {
    if (onOpenCreateDrawer) {
      onOpenCreateDrawer();
    }
  };

  // Column definitions for the table
  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      width: 200,
      minWidth: 120,
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
      width: 250,
      minWidth: 120,
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
            color={
              getStatusColor(params.row.status?.name) as
                | 'warning'
                | 'primary'
                | 'success'
                | 'error'
                | 'default'
            }
            size="small"
          />
        );
      },
    },
    {
      field: 'assignee',
      headerName: 'Assignee',
      width: 150,
      minWidth: 120,
      resizable: true,
      renderCell: params => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Avatar
            src={params.row.assignee?.picture}
            alt={params.row.assignee?.name || 'Unassigned'}
            sx={{
              width: AVATAR_SIZES.SMALL,
              height: AVATAR_SIZES.SMALL,
              bgcolor: 'primary.main',
            }}
          >
            {params.row.assignee?.name?.charAt(0) || 'U'}
          </Avatar>
          <Typography variant="body2">
            {params.row.assignee?.name || 'Unassigned'}
          </Typography>
        </Box>
      ),
    },
  ];

  const createButton = (
    <Button
      variant="outlined"
      startIcon={
        <AddIcon
          sx={{ color: theme => `${theme.palette.primary.main} !important` }}
        />
      }
      onClick={handleCreateTask}
      size="small"
    >
      Create
    </Button>
  );

  if (error) {
    return (
      <TaskErrorBoundary>
        <SectionCard title={`Tasks (${totalCount})`} actions={createButton}>
          <Typography
            variant="body2"
            color="error"
            sx={{ textAlign: 'center', py: 3 }}
          >
            {error}
          </Typography>
        </SectionCard>
      </TaskErrorBoundary>
    );
  }

  if (!loading && tasks.length === 0) {
    return (
      <TaskErrorBoundary>
        <SectionCard>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <TasksIcon
              sx={{
                fontSize: 32,
                color: theme => `${theme.palette.primary.main} !important`,
              }}
            />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No task created yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Create a task to track follow-ups for this{' '}
              {getEntityDisplayName(entityType).toLowerCase()}.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon sx={{ color: 'white !important' }} />}
              onClick={handleCreateTask}
              sx={{ color: 'white' }}
            >
              Create task
            </Button>
          </Box>
        </SectionCard>
      </TaskErrorBoundary>
    );
  }

  return (
    <TaskErrorBoundary>
      <SectionCard title={`Tasks (${totalCount})`} actions={createButton}>
        <BaseDataGrid
          rows={tasks}
          columns={columns}
          loading={loading}
          onRowClick={handleRowClick}
          disableRowSelectionOnClick
          pageSizeOptions={[5, 10, 25]}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          getRowId={row => row.id}
          showToolbar={true}
          disablePaperWrapper={true}
          serverSidePagination={true}
          totalRows={totalCount}
          sx={{
            '& .MuiDataGrid-row': {
              cursor: 'pointer',
            },
            minHeight: Math.min(tasks.length * 52 + 120, 400),
          }}
        />
      </SectionCard>
    </TaskErrorBoundary>
  );
}
