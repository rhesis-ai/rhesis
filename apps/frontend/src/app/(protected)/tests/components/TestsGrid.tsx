'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import AddIcon from '@mui/icons-material/Add';
import ListIcon from '@mui/icons-material/List';
import DeleteIcon from '@mui/icons-material/Delete';
import { 
  GridColDef, 
  GridRowSelectionModel, 
  GridPaginationModel
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Typography, Box, Alert, Avatar, Chip } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestDrawer from './TestDrawer';
import PersonIcon from '@mui/icons-material/Person';
import TestSetSelectionDialog from './TestSetSelectionDialog';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';


interface TestsTableProps {
  sessionToken: string;
  onRefresh?: () => void;
}

export default function TestsTable({ sessionToken, onRefresh }: TestsTableProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const isMounted = useRef(true);
  
  // Component state
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestDetail | undefined>();
  const [testSetDialogOpen, setTestSetDialogOpen] = useState(false);

  useEffect(() => {
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Data fetching function
  const fetchTests = useCallback(async () => {
    if (!sessionToken) return;
    
    try {
      setLoading(true);
      
      const clientFactory = new ApiClientFactory(sessionToken);
      const testsClient = clientFactory.getTestsClient();
      
      const response = await testsClient.getTests({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc'
      });
      
      setTests(response.data);
      setTotalCount(response.pagination.totalCount);
      
      setError(null);
    } catch (error) {
      setError('Failed to load tests');
      setTests([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel.page, paginationModel.pageSize]);

  // Initial data fetch
  useEffect(() => {
    fetchTests();
  }, [fetchTests]);

  // Handle pagination change
  const handlePaginationModelChange = useCallback((newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  }, []);

  // Column definitions
  const columns: GridColDef[] = React.useMemo(() => [
    { 
      field: 'content', 
      headerName: 'Content', 
      flex: 3,
      renderCell: (params) => {
        const content = params.row.prompt?.content || params.row.content;
        if (!content) return null;

        return (
          <Typography 
            variant="body2" 
            title={content}
            sx={{ 
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            {content}
          </Typography>
        );
      }
    },
    { 
      field: 'behavior',
      headerName: 'Behavior', 
      flex: 1,
      renderCell: (params) => {
        const behaviorName = params.row.behavior?.name;
        if (!behaviorName) return null;

        return (
          <Chip 
            label={behaviorName} 
            size="small" 
            variant="outlined"
            color="primary"
          />
        );
      }
    },
    { 
      field: 'topic', 
      headerName: 'Topic', 
      flex: 1,
      renderCell: (params) => {
        const topicName = params.row.topic?.name;
        if (!topicName) return null;

        return (
          <Chip 
            label={topicName} 
            size="small" 
            variant="outlined"
            color="secondary"
          />
        );
      }
    },
    { 
      field: 'category', 
      headerName: 'Category', 
      flex: 1,
      renderCell: (params) => {
        const categoryName = params.row.category?.name;
        if (!categoryName) return null;

        return (
          <Chip 
            label={categoryName} 
            size="small" 
            variant="outlined"
            color="secondary"
          />
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

  // Event handlers
  const handleRowClick = useCallback((params: any) => {
    const testId = params.id;
    router.push(`/tests/${testId}`);
  }, [router]);

  const handleSelectionChange = useCallback((newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  }, []);

  const handleCreateTestSet = useCallback(() => {
    if (selectedRows.length > 0) {
      setTestSetDialogOpen(true);
    }
  }, [selectedRows]);

  const handleTestSetSelect = useCallback(async (testSet: TestSet) => {
    if (!sessionToken) return;
    
    try {
      const testSetsClient = new TestSetsClient(sessionToken);
      await testSetsClient.associateTestsWithTestSet(testSet.id, selectedRows as string[]);
      
      if (isMounted.current) {
        notifications.show(
          `Successfully associated ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'} with test set "${testSet.name}"`,
          {
            severity: 'success',
            autoHideDuration: 6000
          }
        );
        
        setTestSetDialogOpen(false);
      }
    } catch (error) {
      notifications.show(
        'Failed to associate tests with test set',
        {
          severity: 'error',
          autoHideDuration: 6000
        }
      );
    }
  }, [sessionToken, selectedRows, notifications]);

  const handleDeleteTests = useCallback(() => {
    if (selectedRows.length > 0) {
      alert(`Deleting ${selectedRows.length} tests`);
    }
  }, [selectedRows]);

  const handleNewTest = useCallback(() => {
    setSelectedTest(undefined);
    setDrawerOpen(true);
  }, []);

  const generateNewTests = useCallback(() => {
    router.push('/tests/new-generated');
  }, [router]);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTest(undefined);
  }, []);

  const handleTestSaved = useCallback(() => {
    if (sessionToken) {
      fetchTests();
      onRefresh?.();
    }
  }, [sessionToken, fetchTests, onRefresh]);

  const handleGenerateTests = useCallback(() => {
    generateNewTests();
  }, [generateNewTests]);

  // Get action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];

    buttons.push({
      label: 'Write Test',
      icon: <AddIcon />,
      variant: 'contained' as const,
      onClick: handleNewTest,
      splitButton: {
        options: [
          {
            label: 'Write Multiple Tests',
            onClick: () => router.push('/tests/new?multiple=true')
          }
        ]
      }
    });

    buttons.push({
      label: 'Generate Tests',
      icon: <AddIcon />,
      variant: 'contained' as const,
      onClick: handleGenerateTests,
    });

    if (selectedRows.length > 0) {
      buttons.push({
        label: 'Assign to Test Set',
        icon: <ListIcon />,
        variant: 'contained' as const,
        onClick: handleCreateTestSet
      });
      
      buttons.push({
        label: 'Delete Tests',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTests
      });
    }

    return buttons;
  }, [selectedRows.length, handleNewTest, handleCreateTestSet, handleDeleteTests, router, handleGenerateTests]);

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

      {sessionToken && (
        <>
          <TestDrawer
            open={drawerOpen}
            onClose={handleDrawerClose}
            sessionToken={sessionToken}
            test={selectedTest}
            onSuccess={handleTestSaved}
          />
          <TestSetSelectionDialog
            open={testSetDialogOpen}
            onClose={() => setTestSetDialogOpen(false)}
            onSelect={handleTestSetSelect}
            sessionToken={sessionToken}
          />
        </>
      )}
    </>
  );
}