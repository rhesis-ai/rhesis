'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Typography,
  Chip,
  Avatar,
  Alert,
  Grid,
  Paper,
} from '@mui/material';
import { 
  GridColDef, 
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel
} from '@mui/x-data-grid';
import { Task, TaskStatus, TaskPriority, EntityType } from '@/types/tasks';
import { mockTasks, getTaskStats } from '@/utils/mock-data/tasks';
import { UserAvatar } from '@/components/common/UserAvatar';
import { PageContainer } from '@toolpad/core/PageContainer';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Add as AddIcon, Assignment as TaskIcon } from '@mui/icons-material';

export default function TasksPage() {
  const router = useRouter();
  const [tasks] = useState<Task[]>(mockTasks);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const stats = getTaskStats();

  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      // Apply filters based on filterModel
      for (const filter of filterModel.items) {
        if (filter.field === 'status' && filter.value && !filter.value.includes(task.status)) {
          return false;
        }
        if (filter.field === 'priority' && filter.value && !filter.value.includes(task.priority)) {
          return false;
        }
        if (filter.field === 'entity_type' && filter.value && !filter.value.includes(task.entity_type)) {
          return false;
        }
        if (filter.field === 'assignee_name' && filter.value && !task.assignee_name?.toLowerCase().includes(filter.value.toLowerCase())) {
          return false;
        }
      }
      return true;
    });
  }, [tasks, filterModel]);

  // Column definitions
  const columns: GridColDef[] = React.useMemo(() => [
    {
      field: 'title',
      headerName: 'Title',
      flex: 2,
      minWidth: 200,
      filterable: true,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TaskIcon fontSize="small" color="action" />
          <Typography variant="body2" fontWeight={500}>
            {params.value}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      filterable: true,
      renderCell: (params) => (
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            maxWidth: 200,
          }}
        >
          {params.value}
        </Typography>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      filterable: true,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={getStatusColor(params.value)}
          variant="outlined"
        />
      ),
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 100,
      filterable: true,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={getPriorityColor(params.value)}
          variant="outlined"
        />
      ),
    },
    {
      field: 'assignee_name',
      headerName: 'Assignee',
      width: 150,
      filterable: true,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <UserAvatar 
            userName={params.value || params.row.creator_name}
            size={24}
          />
          <Typography variant="body2">
            {params.value || 'Unassigned'}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'entity_type',
      headerName: 'Entity',
      width: 120,
      filterable: true,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {getEntityDisplayName(params.value)}
        </Typography>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 120,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {new Date(params.value).toLocaleDateString()}
        </Typography>
      ),
    },
  ], []);

  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case 'Open':
        return 'default';
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

  const getPriorityColor = (priority: TaskPriority) => {
    switch (priority) {
      case 'Low':
        return 'default';
      case 'Medium':
        return 'warning';
      case 'High':
        return 'error';
      default:
        return 'default';
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

  // Event handlers
  const handleRowClick = useCallback((params: any) => {
    const taskId = params.id;
    router.push(`/tasks/${taskId}`);
  }, [router]);

  const handleSelectionChange = useCallback((newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  }, []);

  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, []);

  const handleCreateTask = useCallback(() => {
    router.push('/tasks/create');
  }, [router]);

  const handleDeleteTasks = useCallback(() => {
    if (selectedRows.length > 0) {
      alert(`Deleting ${selectedRows.length} tasks`);
    }
  }, [selectedRows]);

  // Get action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];

    buttons.push({
      label: 'Create Task',
      icon: <AddIcon />,
      variant: 'contained' as const,
      onClick: handleCreateTask,
    });

    if (selectedRows.length > 0) {
      buttons.push({
        label: 'Delete Tasks',
        icon: <TaskIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTasks
      });
    }

    return buttons;
  }, [selectedRows.length, handleCreateTask, handleDeleteTasks]);

  return (
    <PageContainer title="Tasks" breadcrumbs={[{ title: 'Tasks', path: '/tasks' }]}>
      {/* Stats Cards */}
      <Box sx={{ mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={2.4}>
            <Box sx={{ 
              p: 2, 
              border: '1px solid', 
              borderColor: 'divider', 
              borderRadius: 2,
              textAlign: 'center',
              bgcolor: 'background.paper'
            }}>
              <Typography variant="h4" fontWeight={600}>
                {stats.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Tasks
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Box sx={{ 
              p: 2, 
              border: '1px solid', 
              borderColor: 'divider', 
              borderRadius: 2,
              textAlign: 'center',
              bgcolor: 'background.paper'
            }}>
              <Typography variant="h4" fontWeight={600} color="primary">
                {stats.open}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Open
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Box sx={{ 
              p: 2, 
              border: '1px solid', 
              borderColor: 'divider', 
              borderRadius: 2,
              textAlign: 'center',
              bgcolor: 'background.paper'
            }}>
              <Typography variant="h4" fontWeight={600} color="warning.main">
                {stats.inProgress}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                In Progress
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Box sx={{ 
              p: 2, 
              border: '1px solid', 
              borderColor: 'divider', 
              borderRadius: 2,
              textAlign: 'center',
              bgcolor: 'background.paper'
            }}>
              <Typography variant="h4" fontWeight={600} color="success.main">
                {stats.completed}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Completed
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} sm={6} md={2.4}>
            <Box sx={{ 
              p: 2, 
              border: '1px solid', 
              borderColor: 'divider', 
              borderRadius: 2,
              textAlign: 'center',
              bgcolor: 'background.paper'
            }}>
              <Typography variant="h4" fontWeight={600} color="error.main">
                {stats.cancelled}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Cancelled
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* Table Section */}
      <Paper sx={{ width: '100%', mb: 2, mt: 4 }}>
        <Box sx={{ p: 2 }}>
          {selectedRows.length > 0 && (
            <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="subtitle1" color="primary">
                {selectedRows.length} tasks selected
              </Typography>
            </Box>
          )}
          
          <BaseDataGrid
            rows={filteredTasks}
            columns={columns}
            loading={false}
            getRowId={(row) => row.id}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            actionButtons={getActionButtons()}
            checkboxSelection
            disableRowSelectionOnClick
            onRowSelectionModelChange={handleSelectionChange}
            rowSelectionModel={selectedRows}
            onRowClick={handleRowClick}
            serverSidePagination={false}
            totalRows={filteredTasks.length}
            pageSizeOptions={[10, 25, 50]}
            serverSideFiltering={false}
            onFilterModelChange={handleFilterModelChange}
            showToolbar={true}
          />
        </Box>
      </Paper>
    </PageContainer>
  );
}