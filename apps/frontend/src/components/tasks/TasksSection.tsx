'use client';

import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  Avatar,
} from '@mui/material';
import { AddIcon } from '@/components/icons';
import { Task, EntityType } from '@/types/tasks';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  GridColDef,
  GridPaginationModel,
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
  onCreateTask: (taskData: any) => Promise<void>;
  onEditTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => Promise<void>;
  onNavigateToCreate?: () => void;
  currentUserId: string;
  currentUserName: string;
}

export function TasksSection({
  entityType,
  entityId,
  sessionToken,
  onCreateTask: _onCreateTask,
  onEditTask: _onEditTask,
  onDeleteTask,
  onNavigateToCreate,
  currentUserId: _currentUserId,
  currentUserName: _currentUserName,
}: TasksSectionProps) {
  const router = useRouter();
  const notifications = useNotifications();

  // Component state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

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
          notifications.show(errorMessage, { severity: 'error' });
          setLoading(false);
        }
      }
    };

    fetchTasks();

    return () => {
      abortController.abort();
    };
  }, [currentPage, currentPageSize, entityType, entityId, sessionToken]);

  const _handleDeleteTask = async (taskId: string) => {
    if (onDeleteTask) {
      try {
        await onDeleteTask(taskId);
      } catch (_error) {}
    }
  };

  const handleRowClick = (params: any) => {
    try {
      router.push(`/tasks/${params.id}`);
    } catch (_error) {}
  };

  const handleCreateTask = () => {
    // Use the provided navigation handler if available (includes additional metadata)
    if (onNavigateToCreate) {
      onNavigateToCreate();
    } else {
      // Fallback to direct navigation
      const queryParams = new URLSearchParams({
        entityType,
        entityId,
      });
      router.push(`/tasks/create?${queryParams.toString()}`);
    }
  };

  // Column definitions for the table
  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      width: 200,
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

  return (
    <TaskErrorBoundary>
      <Box>
        {/* Header */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6" component="h2">
            Tasks ({tasks.length})
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateTask}
            sx={{
              color: 'white',
              '& .MuiButton-startIcon': {
                color: 'white',
              },
            }}
          >
            Create Task
          </Button>
        </Box>

        {/* Tasks Table */}
        {error ? (
          <Typography
            variant="body2"
            color="error"
            sx={{ textAlign: 'center', py: 3 }}
          >
            {error}
          </Typography>
        ) : !loading && tasks.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ textAlign: 'center', py: 3 }}
          >
            No tasks yet. Create the first task for this{' '}
            {getEntityDisplayName(entityType).toLowerCase()}.
          </Typography>
        ) : (
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
              minHeight: Math.min(tasks.length * 52 + 120, 400), // Dynamic height
            }}
          />
        )}
      </Box>
    </TaskErrorBoundary>
  );
}
