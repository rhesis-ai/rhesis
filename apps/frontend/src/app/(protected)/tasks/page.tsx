'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { FilterList as FilterIcon } from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { Task, TaskStatus, TaskPriority, EntityType, TaskFilters } from '@/types/tasks';
import { mockTasks, getTaskStats } from '@/utils/mock-data/tasks';
import { UserAvatar } from '@/components/common/UserAvatar';

export default function TasksPage() {
  const router = useRouter();
  const [tasks] = useState<Task[]>(mockTasks);
  const [filters, setFilters] = useState<TaskFilters>({});
  const [mounted, setMounted] = useState(false);

  // Ensure component is mounted before rendering DataGrid
  useEffect(() => {
    setMounted(true);
  }, []);

  const stats = getTaskStats();

  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      if (filters.status && filters.status.length > 0 && !filters.status.includes(task.status)) {
        return false;
      }
      if (filters.priority && filters.priority.length > 0 && !filters.priority.includes(task.priority)) {
        return false;
      }
      if (filters.assignee_id && task.assignee_id !== filters.assignee_id) {
        return false;
      }
      if (filters.entity_type && filters.entity_type.length > 0 && !filters.entity_type.includes(task.entity_type)) {
        return false;
      }
      return true;
    });
  }, [tasks, filters]);


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

  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      flex: 1,
      minWidth: 200,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" fontWeight={500}>
            {params.value}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      minWidth: 200,
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
  ];

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight={600}>
          Tasks
        </Typography>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2.4}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight={600}>
                {stats.total}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total Tasks
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight={600} color="primary">
                {stats.open}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Open
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight={600} color="warning.main">
                {stats.inProgress}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                In Progress
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight={600} color="success.main">
                {stats.completed}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Completed
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          <Card>
            <CardContent sx={{ textAlign: 'center' }}>
              <Typography variant="h4" fontWeight={600} color="error.main">
                {stats.cancelled}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Cancelled
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          <FilterIcon color="action" />
          <Typography variant="subtitle2" fontWeight={600}>
            Filters:
          </Typography>
          
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Status</InputLabel>
            <Select
              multiple
              value={filters.status || []}
              onChange={(e) => setFilters({ ...filters, status: e.target.value as TaskStatus[] })}
              label="Status"
            >
              <MenuItem value="Open">Open</MenuItem>
              <MenuItem value="In Progress">In Progress</MenuItem>
              <MenuItem value="Completed">Completed</MenuItem>
              <MenuItem value="Cancelled">Cancelled</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Priority</InputLabel>
            <Select
              multiple
              value={filters.priority || []}
              onChange={(e) => setFilters({ ...filters, priority: e.target.value as TaskPriority[] })}
              label="Priority"
            >
              <MenuItem value="Low">Low</MenuItem>
              <MenuItem value="Medium">Medium</MenuItem>
              <MenuItem value="High">High</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Entity Type</InputLabel>
            <Select
              multiple
              value={filters.entity_type || []}
              onChange={(e) => setFilters({ ...filters, entity_type: e.target.value as EntityType[] })}
              label="Entity Type"
            >
              <MenuItem value="Test">Test</MenuItem>
              <MenuItem value="TestSet">Test Set</MenuItem>
              <MenuItem value="TestRun">Test Run</MenuItem>
              <MenuItem value="TestResult">Test Result</MenuItem>
            </Select>
          </FormControl>

          <Button
            variant="outlined"
            size="small"
            onClick={() => setFilters({})}
          >
            Clear Filters
          </Button>
        </Box>
      </Paper>

      {/* Tasks Table */}
      <Paper sx={{ height: 600 }}>
        {mounted ? (
          <DataGrid
            rows={filteredTasks}
            columns={columns}
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: {
                paginationModel: { pageSize: 25 },
              },
            }}
            disableRowSelectionOnClick
            onRowClick={(params) => router.push(`/tasks/${params.id}`)}
            sx={{
              border: 0,
              '& .MuiDataGrid-cell': {
                borderBottom: '1px solid',
                borderColor: 'divider',
              },
              '& .MuiDataGrid-columnHeaders': {
                borderBottom: '2px solid',
                borderColor: 'divider',
              },
            }}
          />
        ) : (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" color="text.secondary">
              Loading...
            </Typography>
          </Box>
        )}
      </Paper>

    </Box>
  );
}
