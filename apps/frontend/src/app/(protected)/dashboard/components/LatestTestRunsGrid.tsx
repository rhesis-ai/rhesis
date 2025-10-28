'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography,
  Box,
  CircularProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { User } from '@/utils/api-client/interfaces/user';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { parseISO, format } from 'date-fns';

// Status ID to label mapping
const STATUS_MAP: Record<string, { label: string; color: string }> = {
  'da08d71e-d23e-4956-9326-53b184859287': {
    label: 'Failed',
    color: 'error.main',
  },
  '868a686f-349e-4527-a8dd-f1a3b987aa7b': {
    label: 'Completed',
    color: 'success.main',
  },
  // Add more status mappings as needed
};

// Task state to color mapping
const TASK_STATE_COLORS: Record<string, string> = {
  PROGRESS: 'info.main',
  SUCCESS: 'success.main',
  FAILURE: 'error.main',
  PENDING: 'warning.main',
  // Add more as needed
};

interface LatestTestRunsGridProps {
  sessionToken: string;
}

export default function LatestTestRunsGrid({
  sessionToken,
}: LatestTestRunsGridProps) {
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });
  const [userCache, setUserCache] = useState<Record<string, User>>({});

  // Function to fetch and cache user data
  const fetchAndCacheUsers = useCallback(
    async (
      userIds: string[],
      usersClient: ReturnType<ApiClientFactory['getUsersClient']>
    ): Promise<Record<string, User>> => {
      const newUserCache = { ...userCache };
      let cacheUpdated = false;

      await Promise.all(
        userIds.map(async userId => {
          // Skip if we already have this user cached
          if (newUserCache[userId]) return;

          try {
            const user = await usersClient.getUser(userId);
            newUserCache[userId] = user;
            cacheUpdated = true;
          } catch (e) {
            // Removed console.warn
          }
        })
      );

      if (cacheUpdated) {
        setUserCache(newUserCache);
      }

      return newUserCache;
    },
    [userCache]
  );

  const fetchTestRuns = useCallback(async () => {
    try {
      setLoading(true);
      const apiFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = apiFactory.getTestRunsClient();

      // Use pagination model for skip/limit
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;

      // Get paginated response with total count
      const response = await testRunsClient.getTestRuns({
        skip,
        limit,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      setTestRuns(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch (err) {
      setError('Data currently unavailable');
      setTestRuns([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel]);

  useEffect(() => {
    fetchTestRuns();
  }, [fetchTestRuns]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const testRunsColumns: GridColDef[] = [
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      valueGetter: (_, row) => {
        if (row.status?.name) {
          return row.status.name;
        }
        return row.attributes?.task_state || 'Unknown';
      },
      renderCell: params => {
        // Get color based on status or task_state
        let color = 'text.secondary';
        const row = params.row;

        if (row.status_id && STATUS_MAP[row.status_id]) {
          color = STATUS_MAP[row.status_id].color;
        } else if (
          row.attributes?.task_state &&
          TASK_STATE_COLORS[row.attributes.task_state]
        ) {
          color = TASK_STATE_COLORS[row.attributes.task_state];
        }

        return (
          <Box sx={{ width: '100%', display: 'flex', alignItems: 'center' }}>
            <Typography variant="body2" color={color}>
              {params.value}
            </Typography>
          </Box>
        );
      },
    },
    {
      field: 'started',
      headerName: 'Started',
      width: 180,
      valueGetter: (_, row) => {
        if (!row.attributes?.started_at) return '';
        try {
          return format(
            parseISO(row.attributes.started_at),
            'yyyy-MM-dd HH:mm:ss'
          );
        } catch (e) {
          return '';
        }
      },
    },
    {
      field: 'testSet',
      headerName: 'Test Set',
      width: 220,
      valueGetter: (_, row) => {
        // Direct access to test_set data from test_configuration
        return row.test_configuration?.test_set?.name || 'N/A';
      },
      renderCell: params => {
        const row = params.row;
        const description = row.test_configuration?.test_set?.description || '';

        return (
          <Box sx={{ width: '100%', display: 'flex', alignItems: 'center' }}>
            <Tooltip
              title={description}
              arrow
              PopperProps={{
                sx: { maxWidth: '300px' },
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {params.value}
              </Typography>
            </Tooltip>
          </Box>
        );
      },
    },
    {
      field: 'user',
      headerName: 'Executor',
      width: 220,
      valueGetter: (_, row) => {
        if (row.user) {
          return (
            `${row.user.given_name || ''} ${row.user.family_name || ''}`.trim() ||
            row.user.email ||
            row.user_id
          );
        }
        return row.user_id
          ? `User ID: ${row.user_id.toString().substring(0, 8)}...`
          : 'Unknown';
      },
      renderCell: params => (
        <Box sx={{ width: '100%', display: 'flex', alignItems: 'center' }}>
          <Tooltip title={params.value} arrow>
            <Typography
              variant="body2"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {params.value}
            </Typography>
          </Tooltip>
        </Box>
      ),
    },
    {
      field: 'endpoint',
      headerName: 'Endpoint',
      width: 220,
      valueGetter: (_, row) => {
        // Direct access to endpoint data from test_configuration
        return row.test_configuration?.endpoint?.name || 'N/A';
      },
      renderCell: params => {
        const row = params.row;
        const description = row.test_configuration?.endpoint?.description || '';

        return (
          <Box sx={{ width: '100%', display: 'flex', alignItems: 'center' }}>
            <Tooltip
              title={description}
              arrow
              PopperProps={{
                sx: { maxWidth: '300px' },
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {params.value}
              </Typography>
            </Tooltip>
          </Box>
        );
      },
    },
  ];

  if (loading && testRuns.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        {error && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            {error}
          </Alert>
        )}
      </Box>
      <BaseDataGrid
        rows={testRuns}
        columns={testRunsColumns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        density="compact"
        showToolbar={false}
        linkPath="/test-runs"
        linkField="id"
        disableRowSelectionOnClick
        disablePaperWrapper={true}
      />
    </Box>
  );
}
