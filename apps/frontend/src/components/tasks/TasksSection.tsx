'use client';

import React from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Button,
  Chip,
  Avatar,
} from '@mui/material';
import { AddIcon } from '@/components/icons';
import { Task, EntityType } from '@/types/tasks';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { GridColDef } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { TaskErrorBoundary } from './TaskErrorBoundary';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface TasksSectionProps {
  entityType: EntityType;
  entityId: string;
  tasks: Task[];
  onCreateTask: (taskData: any) => Promise<void>;
  onEditTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => Promise<void>;
  currentUserId: string;
  currentUserName: string;
  isLoading?: boolean;
}

export function TasksSection({
  entityType,
  entityId,
  tasks,
  onCreateTask,
  onEditTask,
  onDeleteTask,
  currentUserId,
  currentUserName,
  isLoading = false,
}: TasksSectionProps) {
  const router = useRouter();

  const handleDeleteTask = async (taskId: string) => {
    if (onDeleteTask) {
      try {
        await onDeleteTask(taskId);
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
    }
  };

  const handleRowClick = (params: any) => {
    try {
      router.push(`/tasks/${params.id}`);
    } catch (error) {
      console.error('Navigation error:', error);
    }
  };

  const handleCreateTask = () => {
    const queryParams = new URLSearchParams({
      entityType,
      entityId,
    });
    router.push(`/tasks/create?${queryParams.toString()}`);
  };

  // Column definitions for the table
  const columns: GridColDef[] = [
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
          >
            Create Task
          </Button>
        </Box>

        {/* Tasks Table */}
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : tasks.length === 0 ? (
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
            loading={isLoading}
            onRowClick={handleRowClick}
            disableRowSelectionOnClick
            pageSizeOptions={[5, 10, 25]}
            paginationModel={{ page: 0, pageSize: 10 }}
            getRowId={row => row.id}
            showToolbar={true}
            disablePaperWrapper={true}
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
