'use client';

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Chip, Avatar } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { AddIcon } from '@/components/icons';
import TasksIcon from '@/components/TasksIcon';
import { Task, EntityType } from '@/types/tasks';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { Can } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
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
import { taskKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface TasksSectionProps {
  entityType: EntityType;
  entityId: string;
  onCreateTask: (taskData: Record<string, unknown>) => Promise<void>;
  onEditTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => Promise<void>;
  /** Opens the in-context task creation drawer */
  onOpenCreateDrawer?: (commentId?: string) => void;
}

export function TasksSection({
  entityType,
  entityId,
  onCreateTask: _onCreateTask,
  onEditTask: _onEditTask,
  onDeleteTask,
  onOpenCreateDrawer,
}: TasksSectionProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { status } = useSession();
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const currentPage = paginationModel.page;
  const currentPageSize = paginationModel.pageSize;
  const filter = `entity_type eq '${entityType}' and entity_id eq ${entityId}`;

  const queryKey = taskKeys.list(
    `${entityType}:${entityId}`,
    currentPage,
    currentPageSize,
    'created_at',
    'desc'
  );

  const {
    data,
    isLoading: loading,
    error,
  } = useQuery({
    queryKey,
    queryFn: async () => {
      const clientFactory = new ApiClientFactory();
      const tasksClient = clientFactory.getTasksClient();
      return tasksClient.getTasks({
        skip: currentPage * currentPageSize,
        limit: currentPageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
        $filter: filter,
      });
    },
    enabled: isAuthenticated(status) && !!entityType && !!entityId,
    placeholderData: prev => prev,
  });

  const tasks: Task[] = data?.data ?? [];
  const totalCount: number = data?.totalCount ?? 0;

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const _handleDeleteTask = async (taskId: string) => {
    if (onDeleteTask) {
      try {
        await onDeleteTask(taskId);
        queryClient.invalidateQueries({ queryKey: taskKeys.all() });
      } catch (err) {
        console.error('Failed to delete task:', err);
      }
    }
  };

  const handleRowClick = (params: GridRowParams) => {
    try {
      router.push(`/tasks/${params.id}`);
    } catch (err) {
      console.error('Failed to navigate to task:', err);
    }
  };

  const handleCreateTask = () => {
    if (onOpenCreateDrawer) {
      onOpenCreateDrawer();
    }
  };

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
                'warning' | 'primary' | 'success' | 'error' | 'default'
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
    <Can capability={Capability.Task.CREATE}>
      <Button
        variant="outlined"
        startIcon={<AddIcon />}
        onClick={handleCreateTask}
        size="small"
      >
        Create
      </Button>
    </Can>
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
            Failed to load tasks
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
            <TasksIcon color="primary" sx={{ fontSize: 32 }} />
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
            <Can capability={Capability.Task.CREATE}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleCreateTask}
              >
                Create task
              </Button>
            </Can>
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
