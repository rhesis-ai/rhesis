'use client';

import { useState, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Typography,
  Button,
  Chip,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress
} from '@mui/material';
import { Add, Assignment } from '@mui/icons-material';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useTasks } from '@/hooks/useTasks';
import { Task, TaskStats } from '@/types/tasks';

export default function TasksPage() {
  const router = useRouter();
  const { tasks, isLoading, error, deleteTask } = useTasks();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const stats: TaskStats = useMemo(() => {
    const total = tasks.length;
    const open = tasks.filter(task => task.status?.name === 'Open').length;
    const inProgress = tasks.filter(task => task.status?.name === 'In Progress').length;
    const completed = tasks.filter(task => task.status?.name === 'Completed').length;
    const cancelled = tasks.filter(task => task.status?.name === 'Cancelled').length;
    
    return { total, open, inProgress, completed, cancelled };
  }, [tasks]);

  const columns = [
    {
      field: 'title',
      headerName: 'Title',
      width: 300,
      renderCell: (params: any) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Assignment fontSize="small" color="action" />
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
      renderCell: (params: any) => {
        const getStatusColor = (status: string) => {
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
      renderCell: (params: any) => {
        const getPriorityColor = (priority: string) => {
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
      field: 'assignee_name',
      headerName: 'Assignee',
      width: 150,
      renderCell: (params: any) => (
        <Typography variant="body2">
          {params.row.assignee?.name || 'Unassigned'}
        </Typography>
      ),
    },
    {
      field: 'creator_name',
      headerName: 'Creator',
      width: 150,
      renderCell: (params: any) => (
        <Typography variant="body2">
          {params.row.user?.name || 'Unknown'}
        </Typography>
      ),
    },
    {
      field: 'entity_type',
      headerName: 'Related To',
      width: 120,
      renderCell: (params: any) => (
        <Typography variant="body2">
          {params.row.entity_type || '-'}
        </Typography>
      ),
    },
  ];

  const handleRowClick = (params: any) => {
    router.push(`/tasks/${params.id}`);
  };

  const handleDeleteTasks = useCallback(async () => {
    if (selectedRows.length > 0) {
      const confirmed = window.confirm(`Are you sure you want to delete ${selectedRows.length} tasks?`);
      if (confirmed) {
        for (const taskId of selectedRows) {
          await deleteTask(taskId as string);
        }
        setSelectedRows([]);
      }
    }
  }, [selectedRows, deleteTask]);

  const StatCard = ({ title, value, color = 'primary' }: { title: string; value: number; color?: string }) => (
    <Card>
      <CardContent>
        <Typography color="textSecondary" gutterBottom variant="h6">
          {title}
        </Typography>
        <Typography variant="h4" color={`${color}.main`}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );

  return (
    <PageContainer title="Tasks" breadcrumbs={[{ title: 'Tasks', path: '/tasks' }]}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => router.push('/tasks/create')}
        >
          Create Task
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Total" value={stats.total} />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Open" value={stats.open} color="warning" />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="In Progress" value={stats.inProgress} color="info" />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Completed" value={stats.completed} color="success" />
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <StatCard title="Cancelled" value={stats.cancelled} color="error" />
        </Grid>
      </Grid>

      {/* Tasks Table */}
      <BaseDataGrid
        rows={tasks}
        columns={columns}
        loading={isLoading}
        onRowClick={handleRowClick}
        checkboxSelection
        onRowSelectionModelChange={(newSelection: any) => setSelectedRows(newSelection as string[])}
        getRowId={(row: any) => row.id}
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row': {
            cursor: 'pointer',
          },
        }}
      />

      {/* Bulk Actions */}
      {selectedRows.length > 0 && (
        <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            color="error"
            onClick={handleDeleteTasks}
            disabled={isLoading}
          >
            Delete Selected ({selectedRows.length})
          </Button>
        </Box>
      )}
    </PageContainer>
  );
}