'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, Box, CircularProgress, Alert, Chip } from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDistanceToNow, parseISO, format } from 'date-fns';

interface RecentTestsGridProps {
  sessionToken: string;
}

export default function RecentTestsGrid({
  sessionToken,
}: RecentTestsGridProps) {
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });

  const fetchTests = useCallback(async () => {
    try {
      setLoading(true);

      // Calculate skip based on pagination model
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;

      const client = new ApiClientFactory(sessionToken).getTestsClient();
      const response = await client.getTests({
        skip,
        limit,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setTests(response.data);
      setTotalCount(response.pagination.totalCount);
      setError(null);
    } catch (err) {
      setError('Data currently unavailable');
      setTests([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel]);

  useEffect(() => {
    fetchTests();
  }, [fetchTests]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const testColumns: GridColDef[] = [
    {
      field: 'behavior',
      headerName: 'Behavior',
      width: 120,
      valueGetter: (_, row) => row.behavior?.name || 'Unspecified',
    },
    {
      field: 'topic',
      headerName: 'Topic',
      width: 120,
      valueGetter: (_, row) => row.topic?.name || 'Uncategorized',
    },
    {
      field: 'prompt',
      headerName: 'Prompt',
      flex: 1,
      minWidth: 100,
      valueGetter: (_, row) => row.prompt?.content || 'No prompt',
    },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 140,
      sortable: false,
      renderCell: params => {
        const test = params.row;
        if (!test.tags || test.tags.length === 0) {
          return null;
        }

        return (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {test.tags
              .filter(tag => tag && tag.id && tag.name)
              .slice(0, 2)
              .map((tag: Tag) => (
                <Chip
                  key={tag.id}
                  label={tag.name}
                  size="small"
                  variant="filled"
                  color="primary"
                />
              ))}
            {test.tags.filter(tag => tag && tag.id && tag.name).length > 2 && (
              <Chip
                label={`+${test.tags.filter(tag => tag && tag.id && tag.name).length - 2}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        );
      },
    },
  ];

  if (loading && tests.length === 0) {
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
        rows={tests}
        columns={testColumns}
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
