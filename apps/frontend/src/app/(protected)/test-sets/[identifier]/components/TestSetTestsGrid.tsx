'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Typography, Box, Alert, Button, Chip } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { useNotifications } from '@/components/common/NotificationContext';
import DeleteIcon from '@mui/icons-material/Delete';
import { isMultiTurnTest } from '@/constants/test-types';
import { isMultiTurnConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';

interface TestSetTestsGridProps {
  sessionToken: string;
  testSetId: string;
  onRefresh?: () => void;
}

export default function TestSetTestsGrid({
  sessionToken,
  testSetId,
  onRefresh,
}: TestSetTestsGridProps) {
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
        sort_by: 'topic',
        sort_order: 'asc',
      });

      if (isMounted.current) {
        setTests(response.data);
        setTotalCount(response.pagination.totalCount);
        setError(null);
      }
    } catch (error) {
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

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = React.useMemo(
    () => [
      {
        field: 'prompt.content',
        headerName: 'Content',
        flex: 3,
        valueGetter: (value, row) => {
          // For multi-turn tests, show the goal
          if (
            isMultiTurnTest(row.test_type?.type_value) &&
            isMultiTurnConfig(row.test_configuration)
          ) {
            return row.test_configuration.goal || '';
          }
          // For single-turn tests, show the prompt content
          return row.prompt?.content || '';
        },
        renderCell: params => {
          let content = '';

          // For multi-turn tests, show the goal
          if (
            isMultiTurnTest(params.row.test_type?.type_value) &&
            isMultiTurnConfig(params.row.test_configuration)
          ) {
            content = params.row.test_configuration.goal || '';
          } else {
            // For single-turn tests, show the prompt content
            content = params.row.prompt?.content || '';
          }

          if (!content) return null;

          return (
            <Typography
              variant="body2"
              title={content}
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {content}
            </Typography>
          );
        },
      },
      {
        field: 'behavior',
        headerName: 'Behavior',
        flex: 1,
        renderCell: params => {
          const behaviorName = params.row.behavior?.name;
          if (!behaviorName) return null;

          return (
            <Chip
              label={behaviorName}
              variant="outlined"
              size="small"
              color="default"
            />
          );
        },
      },
      {
        field: 'topic',
        headerName: 'Topic',
        flex: 1,
        renderCell: params => {
          const topicName = params.row.topic?.name;
          if (!topicName) return null;

          return (
            <Chip
              label={topicName}
              variant="outlined"
              size="small"
              color="default"
            />
          );
        },
      },
      {
        field: 'category',
        headerName: 'Category',
        flex: 1,
        renderCell: params => {
          const categoryName = params.row.category?.name;
          if (!categoryName) return null;

          return (
            <Chip
              label={categoryName}
              variant="outlined"
              size="small"
              color="default"
            />
          );
        },
      },
      {
        field: 'test_type.type_value',
        headerName: 'Test Type',
        flex: 1,
        valueGetter: (value, row) => row.test_type?.type_value || '',
        renderCell: params => {
          const testType = params.row.test_type?.type_value;
          if (!testType) return null;

          return <Chip label={testType} size="small" variant="outlined" />;
        },
      },
    ],
    []
  );

  // Handle row click to navigate to test details
  const handleRowClick = useCallback(
    (params: any) => {
      const testId = params.id;
      router.push(`/tests/${testId}`);
    },
    [router]
  );

  // Handle row selection change
  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

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
      await testSetsClient.disassociateTestsFromTestSet(
        testSetId,
        selectedRows as string[]
      );

      notifications.show(
        `Successfully removed ${selectedRows.length} ${selectedRows.length === 1 ? 'test' : 'tests'} from test set`,
        {
          severity: 'success',
          autoHideDuration: 6000,
        }
      );

      // Refresh the data
      fetchTests();
      onRefresh?.();
    } catch (error) {
      notifications.show('Failed to remove tests from test set', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    }
  }, [
    sessionToken,
    testSetId,
    selectedRows,
    fetchTests,
    onRefresh,
    notifications,
  ]);

  // Dynamic action buttons based on selection
  const getActionButtons = useCallback(() => {
    const buttons = [];

    if (selectedRows.length > 0) {
      buttons.push({
        label: `Remove ${selectedRows.length} ${selectedRows.length === 1 ? 'Test' : 'Tests'}`,
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleRemoveTests,
      });
    }

    return buttons;
  }, [selectedRows.length, handleRemoveTests]);

  return (
    <>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Tests
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}

      {selectedRows.length > 0 && (
        <Box
          sx={{
            mb: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} tests selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        rows={tests}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
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
        disablePaperWrapper={true}
      />
    </>
  );
}
