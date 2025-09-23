'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { AddIcon, DeleteIcon } from '@/components/icons';
import { 
  GridColDef, 
  GridRowSelectionModel, 
  GridPaginationModel,
  GridFilterModel
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Task } from '@/utils/api-client/interfaces/task';
import { Typography, Box, Alert, Chip, Button, Avatar } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
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

  // Fetch tasks
  const fetchTasks = useCallback(async () => {
    if (!isMounted.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const clientFactory = new ApiClientFactory(sessionToken);
      const tasksClient = clientFactory.getTasksClient();
      
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;
      
      // Convert filter model to OData filter (includes both regular filters and quick filter)
      const oDataFilter = combineTaskFiltersToOData(filterModel);
      
      // Debug logging for search functionality
      if (oDataFilter) {
        console.log('🔍 Task search/filter OData:', oDataFilter);
      }
      
      const response = await tasksClient.getTasks({
        skip,
        limit,
        sort_by: 'nano_id',
        sort_order: 'desc',
        $filter: oDataFilter
      });
      
      if (isMounted.current) {
        setTasks(response);
        // Note: Backend should return total count in headers, but for now we'll estimate
        setTotalCount(response.length < limit ? skip + response.length : skip + response.length + 1);
      }
    } catch (err) {
      if (isMounted.current) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch tasks';
        setError(errorMessage);
        notifications.show(errorMessage, { severity: 'error' });
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [sessionToken, paginationModel, filterModel, notifications]);

  // Delete task
  const deleteTask = useCallback(async (taskId: string) => {
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const tasksClient = clientFactory.getTasksClient();
      
      await tasksClient.deleteTask(taskId);
      
      // Remove from local state
      setTasks(prev => prev.filter(task => task.id !== taskId));
      setSelectedRows(prev => prev.filter(id => id !== taskId));
      
      notifications.show('Task deleted successfully', { severity: 'success' });
      onRefresh?.();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete task';
      notifications.show(errorMessage, { severity: 'error' });
    }
  }, [sessionToken, notifications, onRefresh]);

  // Delete selected tasks
  const handleDeleteSelected = useCallback(async () => {
    if (selectedRows.length === 0) return;
    
    const confirmed = window.confirm(`Are you sure you want to delete ${selectedRows.length} task(s)?`);
    if (!confirmed) return;
    
    try {
      await Promise.all(selectedRows.map(id => deleteTask(id as string)));
      setSelectedRows([]);
    } catch (err) {
      console.error('Error deleting tasks:', err);
    }
  }, [selectedRows, deleteTask]);

  // Handle row click
  const handleRowClick = useCallback((params: any) => {
    router.push(`/tasks/${params.id}`);
  }, [router]);

  // Handle pagination change
  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  // Handle filter change
  const handleFilterModelChange = useCallback((newModel: GridFilterModel) => {
    setFilterModel(newModel);
  }, []);

  // Fetch tasks when dependencies change
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Cleanup
  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Column definitions
  const columns: GridColDef[] = [
    {
      field: 'title',
      headerName: 'Title',
      width: 300,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
          {params.row.title}
        </Typography>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      width: 400,
      renderCell: (params) => (
        <Typography variant="body2" sx={{ 
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: '100%'
        }}>
          {params.row.description || '-'}
        </Typography>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => {
        const getStatusColor = (status?: string) => {
          switch (status) {
            case 'Open': return 'warning';
            case 'In Progress': return 'primary';
            case 'Completed': return 'success';
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
      field: 'assignee',
      headerName: 'Assignee',
      width: 150,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Avatar 
            src={params.row.assignee?.picture} 
            alt={params.row.assignee?.name || 'Unassigned'}
            sx={{ width: AVATAR_SIZES.SMALL, height: AVATAR_SIZES.SMALL, bgcolor: 'primary.main' }}
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
        onRowClick={handleRowClick}
        checkboxSelection
        onRowSelectionModelChange={setSelectedRows}
        rowSelectionModel={selectedRows}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        onFilterModelChange={handleFilterModelChange}
        pageSizeOptions={[10, 25, 50, 100]}
        getRowId={(row) => row.id}
        disableRowSelectionOnClick
        showToolbar={true}
        serverSidePagination={true}
        totalRows={totalCount}
        serverSideFiltering={true}
        enableQuickFilter={true}
        disablePaperWrapper={true}
        actionButtons={[
          {
            label: 'Create Task',
            onClick: () => router.push('/tasks/create'),
            icon: <AddIcon />,
            variant: 'contained' as const,
            color: 'primary' as const
          },
          ...(selectedRows.length > 0 ? [{
            label: `Delete (${selectedRows.length})`,
            onClick: handleDeleteSelected,
            icon: <DeleteIcon />,
            variant: 'outlined' as const,
            color: 'error' as const
          }] : [])
        ]}
        sx={{
          '& .MuiDataGrid-row': {
            cursor: 'pointer',
          },
        }}
      />
    </Box>
  );
}
