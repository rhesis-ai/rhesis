'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteIcon from '@mui/icons-material/Delete';
import { GridColDef, GridRowSelectionModel, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Typography, Box, CircularProgress, Alert, Avatar, Button, Chip } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import PersonIcon from '@mui/icons-material/Person';
import { useNotifications } from '@/components/common/NotificationContext';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import TestRunDrawer from './TestRunDrawer';

interface ProjectCache {
  [key: string]: string;
}

interface TestRunsTableProps {
  sessionToken: string;
  onRefresh?: () => void;
}

export default function TestRunsTable({ sessionToken, onRefresh }: TestRunsTableProps) {
  const isMounted = useRef(false);
  const router = useRouter();
  const notifications = useNotifications();
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [projectNames, setProjectNames] = useState<ProjectCache>({});
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  });

  const fetchProjectName = useCallback(async (projectId: string) => {
    if (!sessionToken || projectNames[projectId]) return;

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const projectsClient = clientFactory.getProjectsClient();
      const project = await projectsClient.getProject(projectId);
      
      if (isMounted.current) {
        setProjectNames(prev => ({
          ...prev,
          [projectId]: project.name
        }));
      }
    } catch (err) {
      console.error('Error fetching project:', err);
    }
  }, [sessionToken, projectNames]);

  const fetchTestRuns = useCallback(async (skip: number, limit: number) => {
    if (!sessionToken) return;
    
    try {
      if (isMounted.current) {
        setLoading(true);
      }
      
      const clientFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = clientFactory.getTestRunsClient();
      
      const response = await testRunsClient.getTestRuns({
        skip,
        limit,
        sortBy: 'created_at',
        sortOrder: 'desc'
      });
      
      if (isMounted.current) {
        setTestRuns(response.data);
        setTotalCount(response.pagination.totalCount);
        setError(null);

        // Fetch project names for new test runs
        const projectIds = response.data
          .map(run => run.test_configuration?.endpoint?.project_id)
          .filter((id): id is string => !!id && !projectNames[id]);

        // Fetch unique project names
        const uniqueProjectIds = [...new Set(projectIds)];
        uniqueProjectIds.forEach(projectId => {
          fetchProjectName(projectId);
        });
      }
    } catch (error) {
      console.error('Error fetching test runs:', error);
      if (isMounted.current) {
        setError('Failed to load test runs');
        setTestRuns([]);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [sessionToken, projectNames, fetchProjectName]);

  useEffect(() => {
    isMounted.current = true;

    const loadData = async () => {
      if (!sessionToken) return;
      
      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchTestRuns(skip, paginationModel.pageSize);
    };

    loadData();

    return () => {
      isMounted.current = false;
    };
  }, [sessionToken, paginationModel, fetchTestRuns]);

  const columns: GridColDef[] = React.useMemo(() => [
    { 
      field: 'name',
      headerName: 'Name', 
      flex: 1,
      valueGetter: (_, row) => row.name || ''
    },
    { 
      field: 'test_sets',
      headerName: 'Test Sets',
      flex: 1,
      valueGetter: (_, row) => {
        const testSet = row.test_configuration?.test_set;
        return testSet?.name || '';
      }
    },
    { 
      field: 'total_tests',
      headerName: 'Total Tests',
      flex: 1,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (_, row) => {
        const metadata = row.test_configuration?.test_set?.attributes?.metadata;
        return metadata?.total_tests || 0;
      }
    },
    { 
      field: 'execution_time',
      headerName: 'Execution Time (sec)', 
      flex: 1,
      align: 'right',
      headerAlign: 'right',
      valueGetter: (_, row) => {
        const status = row.status?.name || row.attributes?.status;
        if (status?.toLowerCase() !== 'completed') return '';
        
        const timeMs = row.attributes?.total_execution_time_ms;
        if (!timeMs) return '';
        return Math.round(timeMs / 1000); // Convert ms to seconds and round
      }
    },
    { 
      field: 'status', 
      headerName: 'Status', 
      flex: 1,
      renderCell: (params) => {
        const status = params.row.status?.name;
        if (!status) return null;

        return (
          <Chip 
            label={status} 
            size="small" 
            variant="outlined" 
          />
        );
      }
    },
    { 
      field: 'executor', 
      headerName: 'Executor', 
      flex: 1,
      renderCell: (params) => {
        const executor = params.row.user;
        if (!executor) return null;

        const displayName = executor.name || 
          `${executor.given_name || ''} ${executor.family_name || ''}`.trim() || 
          executor.email;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar
              src={executor.picture}
              sx={{ width: 24, height: 24 }}
            >
              <PersonIcon />
            </Avatar>
            <Typography variant="body2">{displayName}</Typography>
          </Box>
        );
      }
    }
  ], [projectNames]);

  // Handle row click to navigate to test run details
  const handleRowClick = useCallback((params: any) => {
    const testRunId = params.id;
    router.push(`/test-runs/${testRunId}`);
  }, [router]);

  // Handle row selection change
  const handleSelectionChange = useCallback((newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  }, []);

  // Handle new test run
  const handleCreateTestRun = useCallback(() => {
    setIsDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setIsDrawerOpen(false);
  }, []);

  const handleDrawerSuccess = useCallback(() => {
    const skip = paginationModel.page * paginationModel.pageSize;
    fetchTestRuns(skip, paginationModel.pageSize);
    onRefresh?.();
  }, [fetchTestRuns, onRefresh, paginationModel]);

  // Handle delete selected test runs
  const handleDeleteTestRuns = useCallback(async () => {
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];
    if (validSelectedRows.length > 0) {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();
        const statusClient = clientFactory.getStatusClient();
        
        // Get the "Deleted" status
        const statuses = await statusClient.getStatuses({ entity_type: 'TestRun' });
        const deletedStatus = statuses.find(s => s.name.toLowerCase() === 'deleted');
        
        if (!deletedStatus) {
          throw new Error('Could not find Deleted status');
        }
        
        await Promise.all(
          validSelectedRows.map(id => testRunsClient.updateTestRun(id.toString(), { 
            status_id: deletedStatus.id 
          }))
        );
        
        notifications.show(`Successfully deleted ${validSelectedRows.length} test runs`, { severity: 'success' });
        
        // Refresh the data
        const skip = paginationModel.page * paginationModel.pageSize;
        await fetchTestRuns(skip, paginationModel.pageSize);
        
        // Clear selection
        setSelectedRows([]);
      } catch (error) {
        console.error('Error deleting test runs:', error);
        notifications.show('Failed to delete test runs', { severity: 'error' });
      }
    }
  }, [selectedRows, sessionToken, notifications, paginationModel, fetchTestRuns]);

  // Dynamic action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];

    buttons.push({
      label: 'New Test Run',
      icon: <AddIcon />,
      variant: 'contained' as const,
      onClick: handleCreateTestRun
    });

    if (validSelectedRows.length > 0) {
      buttons.push({
        label: 'Delete Test Runs',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTestRuns
      });
    }

    return buttons;
  }, [selectedRows, handleCreateTestRun, handleDeleteTestRuns]);

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {Array.isArray(selectedRows) && selectedRows.length > 0 && (
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} test runs selected
          </Typography>
        </Box>
      )}
      
      <BaseDataGrid
        rows={testRuns}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={(model) => {
          setPaginationModel(model);
          const skip = model.page * model.pageSize;
          fetchTestRuns(skip, model.pageSize);
        }}
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={Array.isArray(selectedRows) ? selectedRows : []}
        onRowClick={handleRowClick}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        checkboxSelection
        disableRowSelectionOnClick
        actionButtons={getActionButtons()}
      />

      <TestRunDrawer
        open={isDrawerOpen}
        onClose={handleDrawerClose}
        sessionToken={sessionToken}
        onSuccess={handleDrawerSuccess}
      />
    </>
  );
} 