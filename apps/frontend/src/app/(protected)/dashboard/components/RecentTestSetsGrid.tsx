'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, Box, CircularProgress, Alert, Chip } from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { formatDistanceToNow, parseISO, format } from 'date-fns';
import { Organization } from '@/utils/api-client/interfaces/organization';

interface RecentTestSetsGridProps {
  sessionToken: string;
}

export default function RecentTestSetsGrid({
  sessionToken,
}: RecentTestSetsGridProps) {
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<
    Record<string, Organization>
  >({});
  const [validOrgIds, setValidOrgIds] = useState<Set<string>>(new Set());
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });

  const fetchTestSets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Calculate skip based on pagination model
      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      const response = await testSetsClient.getTestSets({
        skip,
        limit,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      setTestSets(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch (error) {
      console.error('Error fetching test sets:', error);
      setError('Data currently unavailable');
      setTestSets([]);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, paginationModel]);

  useEffect(() => {
    fetchTestSets();
  }, [fetchTestSets]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const testSetsColumns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 120,
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      minWidth: 220,
      valueGetter: (_, row) =>
        row.short_description || row.description || 'No description',
    },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 140,
      sortable: false,
      renderCell: params => {
        const testSet = params.row;
        if (!testSet.tags || testSet.tags.length === 0) {
          return null;
        }

        return (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {testSet.tags.slice(0, 2).map(tag => (
              <Chip
                key={tag.id}
                label={tag.name}
                size="small"
                variant="filled"
                color="primary"
              />
            ))}
            {testSet.tags.length > 2 && (
              <Chip
                label={`+${testSet.tags.length - 2}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        );
      },
    },
  ];

  if (loading && testSets.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <BaseDataGrid
        rows={testSets}
        columns={testSetsColumns}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        loading={loading}
        showToolbar={false}
        density="compact"
        linkPath="/test-sets"
        linkField="id"
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        disableRowSelectionOnClick
        disablePaperWrapper={true}
      />
    </Box>
  );
}
