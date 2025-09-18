'use client';

import React from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Button,
  Chip,
} from '@mui/material';
import { Add as AddIcon, Assignment as AssignmentIcon } from '@mui/icons-material';
import { Task, EntityType } from '@/types/tasks';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { GridColDef } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';

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

  const getEntityDisplayName = (entityType: EntityType): string => {
    switch (entityType) {
      case 'Test':
        return 'Test';
      case 'TestSet':
        return 'Test Set';
      case 'TestRun':
        return 'Test Run';
      case 'TestResult':
        return 'Test Result';
      default:
        return entityType;
    }
  };

  const handleRowClick = (params: any) => {
    router.push(`/tasks/${params.id}`);
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
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AssignmentIcon fontSize="small" color="action" />
          <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
            {params.row.title}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => {
        const getStatusColor = (status?: string) => {
          switch (status) {
            case 'Completed': return 'success';
            case 'In Progress': return 'primary';
            case 'Cancelled': return 'error';
            default: return 'default';
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
      field: 'priority',
      headerName: 'Priority',
      width: 120,
      renderCell: (params) => {
        const getPriorityColor = (priority?: string) => {
          switch (priority) {
            case 'High': return 'error';
            case 'Medium': return 'warning';
            case 'Low': return 'default';
            default: return 'default';
          }
        };
        
        return (
          <Chip 
            label={params.row.priority?.type_value || 'Unknown'} 
            color={getPriorityColor(params.row.priority?.type_value) as any}
            size="small"
          />
        );
      },
    },
    {
      field: 'assignee',
      headerName: 'Assignee',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.row.assignee?.name || 'Unassigned'}
        </Typography>
      ),
    },
    {
      field: 'user',
      headerName: 'Creator',
      width: 150,
      renderCell: (params) => (
        <Typography variant="body2">
          {params.row.user?.name || 'Unknown'}
        </Typography>
      ),
    },
  ];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
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
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
          No tasks yet. Create the first task for this {getEntityDisplayName(entityType).toLowerCase()}.
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
          getRowId={(row) => row.id}
          showToolbar={true}
          sx={{
            '& .MuiDataGrid-row': {
              cursor: 'pointer',
            },
            minHeight: Math.min(tasks.length * 52 + 120, 400), // Dynamic height
          }}
        />
      )}
    </Box>
  );
}