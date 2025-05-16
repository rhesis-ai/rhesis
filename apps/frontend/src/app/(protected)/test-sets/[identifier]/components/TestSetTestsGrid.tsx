'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { GridColDef, GridRowSelectionModel, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Typography, Box, Alert, Avatar, Button } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import PersonIcon from '@mui/icons-material/Person';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import DeleteIcon from '@mui/icons-material/Delete';

interface TestSetTestsGridProps {
  sessionToken: string;
  testSetId: string;
  onRefresh?: () => void;
}

export default function TestSetTestsGrid({ sessionToken, testSetId, onRefresh }: TestSetTestsGridProps) {
  const isMounted = useRef(true);
  const router = useRouter();
  const notifications = useNotifications();
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 50,
  });

  // Data fetching function
  const fetchTests = useCallback(async () => {
    if (!sessionToken || !testSetId) return;
    
    try {
      if (isMounted.current) {
        setLoading(true);
      }
      
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      
      const response = await testSetsClient.getTestSetTests(testSetId, {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sortBy: 'created_at',
        sortOrder: 'desc'
      });
      
      if (isMounted.current) {
        setTests(response.data);
        setTotalCount(response.pagination.totalCount);
        setError(null);
      }
    } catch (error) {
      console.error('Error fetching test set tests:', error);
      if (isMounted.current) {
        setError('Failed to load tests');
        setTests([]);
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  }, [sessionToken, testSetId, paginationModel.page, paginationModel.pageSize]);

  useEffect(() => {
    isMounted.current = true;
    fetchTests();
    return () => {
      isMounted.current = false;
    };
  }, [fetchTests]);

  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  const columns: GridColDef[] = React.useMemo(() => [
    { 
      field: 'behavior',
      headerName: 'Behavior', 
      flex: 1,
      valueGetter: (_, row) => row.behavior?.name || ''
    },
    { 
      field: 'test_type', 
      headerName: 'Type', 
      flex: 1,
      valueGetter: (_, row) => row.test_type?.type_value || ''
    },
    { 
      field: 'topic', 
      headerName: 'Topic', 
      flex: 1,
      valueGetter: (_, row) => row.topic?.name || ''
    },
    { 
      field: 'category', 
      headerName: 'Category', 
      flex: 1,
      valueGetter: (_, row) => row.category?.name || ''
    },
    { 
      field: 'priority', 
      headerName: 'Priority', 
      flex: 1,
      valueGetter: (_, row) => {
        const priorityLevel = row.priorityLevel;
        return priorityLevel || 'Medium';
      }
    },
    { 
      field: 'status', 
      headerName: 'Status', 
      flex: 1,
      renderCell: (params) => {
        const status = params.row.status;
        if (!status) return null;

        return (
          <Typography variant="body2">
            {status.name}
          </Typography>
        );
      }
    },
    { 
      field: 'assignee', 
      headerName: 'Assignee', 
      flex: 1,
      renderCell: (params) => {
        const assignee = params.row.assignee;
        if (!assignee) return null;

        const displayName = assignee.name || 
          `${assignee.given_name || ''} ${assignee.family_name || ''}`.trim() || 
          assignee.email;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar
              src={assignee.picture}
              sx={{ width: 24, height: 24 }}
            >
              <PersonIcon />
            </Avatar>
            <Typography variant="body2">{displayName}</Typography>
          </Box>
        );
      }
    }
  ], []);

  // Handle row click to navigate to test details
  const handleRowClick = useCallback((params: any) => {
    const testId = params.id;
    router.push(`/tests/${testId}`);
  }, [router]);

  // Handle row selection change
  const handleSelectionChange = useCallback((newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  }, []);

  const handleTestSaved = useCallback(() => {
    if (sessionToken) {
      fetchTests();
      onRefresh?.();
    }
  }, [sessionToken, fetchTests, onRefresh]);

  // Handle removing tests from test set
  const handleRemoveTests = useCallback(async () => {
    if (!sessionToken || !testSetId || selectedRows.length === 0) return;
    
    try {
      const testSetsClient = new TestSetsClient(sessionToken);
      await testSetsClient.disassociateTestsFromTestSet(testSetId, selectedRows as string[]);
      
      notifications.show(
        `Successfully removed ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'} from test set`,
        {
          severity: 'success',
          autoHideDuration: 6000
        }
      );
      
      // Refresh the data
      fetchTests();
      onRefresh?.();
    } catch (error) {
      console.error('Error removing tests from test set:', error);
      
      notifications.show(
        'Failed to remove tests from test set',
        {
          severity: 'error',
          autoHideDuration: 6000
        }
      );
    }
  }, [sessionToken, testSetId, selectedRows, fetchTests, onRefresh, notifications]);

  // Dynamic action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];

    if (selectedRows.length > 0) {
      buttons.push({
        label: `Remove ${selectedRows.length} ${selectedRows.length === 1 ? 'Test' : 'Tests'}`,
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleRemoveTests
      });
    }

    return buttons;
  }, [selectedRows.length, handleRemoveTests]);

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {selectedRows.length > 0 && (
        <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} tests selected
          </Typography>
        </Box>
      )}
      
      <BaseDataGrid
        rows={tests}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        onRowClick={handleRowClick}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
      />
    </>
  );
} 