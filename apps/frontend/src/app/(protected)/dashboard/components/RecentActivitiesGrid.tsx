'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import { Box, CircularProgress, Alert, Typography } from '@mui/material';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDistanceToNow, parseISO, format } from 'date-fns';

interface RecentActivitiesGridProps {
  sessionToken: string;
}

const recentActivitiesColumns: GridColDef[] = [
  {
    field: 'behavior',
    headerName: 'Behavior',
    width: 130,
    valueGetter: (_, row) => row.behavior?.name || 'Unspecified',
  },
  {
    field: 'topic',
    headerName: 'Topic',
    width: 130,
    valueGetter: (_, row) => row.topic?.name || 'Uncategorized',
  },
  {
    field: 'timestamp',
    headerName: 'Update Time',
    flex: 1,
    valueGetter: (_, row) => {
      return row.updated_at
        ? format(parseISO(row.updated_at), 'yyyy-MM-dd HH:mm')
        : '';
    },
  },
];

export default function RecentActivitiesGrid({
  sessionToken,
}: RecentActivitiesGridProps) {
  const [activities, setActivities] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });

  const fetchRecentActivities = useCallback(async () => {
    try {
      setLoading(true);

      // Calculate skip based on pagination model
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;

      const client = new ApiClientFactory(sessionToken).getTestsClient();
      const response = await client.getTests({
        skip,
        limit,
        sort_by: 'updated_at',
        sort_order: 'desc',
      });
      setActivities(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch (err) {
      setError('Data currently unavailable');
      setActivities([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel]);

  useEffect(() => {
    fetchRecentActivities();
  }, [fetchRecentActivities]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  if (loading && activities.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <BaseDataGrid
        rows={activities}
        columns={recentActivitiesColumns}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        loading={loading}
        showToolbar={false}
        density="compact"
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        linkPath="/tests"
        linkField="id"
        disableRowSelectionOnClick
        disablePaperWrapper={true}
      />
    </Box>
  );
}
