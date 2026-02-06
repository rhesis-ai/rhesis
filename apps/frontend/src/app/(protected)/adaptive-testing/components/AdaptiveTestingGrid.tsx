'use client';

import React, { useState, useCallback } from 'react';
import {
  GridColDef,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Box, Chip, Typography } from '@mui/material';
import { AdaptiveTestSet } from '@/utils/api-client/interfaces/adaptive-testing';

interface AdaptiveTestingGridProps {
  testSets: AdaptiveTestSet[];
  loading: boolean;
  sessionToken?: string;
}

export default function AdaptiveTestingGrid({
  testSets,
  loading,
}: AdaptiveTestingGridProps) {
  const router = useRouter();
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.5,
      minWidth: 200,
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 2,
      minWidth: 200,
      renderCell: params => (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {params.value || '-'}
        </Typography>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: params => {
        const status = params.value;
        if (!status) return '-';
        return (
          <Chip
            label={status}
            size="small"
            variant="outlined"
          />
        );
      },
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 160,
      renderCell: params => {
        if (!params.value) return '-';
        return (
          <Typography variant="body2">
            {new Date(params.value).toLocaleDateString()}
          </Typography>
        );
      },
    },
  ];

  const handleRowClick = (params: any) => {
    router.push(`/adaptive-testing/${params.id}`);
  };

  return (
    <Box>
      {testSets.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography
            variant="body1"
            color="text.secondary"
          >
            No adaptive testing test sets found. Create a
            test set with the &quot;Adaptive Testing&quot;
            behavior to get started.
          </Typography>
        </Box>
      ) : (
        <BaseDataGrid
          columns={columns}
          rows={testSets}
          loading={loading}
          getRowId={row => row.id}
          showToolbar={false}
          onRowClick={handleRowClick}
          paginationModel={paginationModel}
          onPaginationModelChange={
            handlePaginationModelChange
          }
          serverSidePagination={false}
          totalRows={testSets.length}
          pageSizeOptions={[10, 25, 50]}
          disablePaperWrapper={true}
          persistState
        />
      )}
    </Box>
  );
}
