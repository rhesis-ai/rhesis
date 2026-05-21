'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import AddIcon from '@mui/icons-material/Add';
import RouteOutlinedIcon from '@mui/icons-material/RouteOutlined';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import TestSetSelectionDialog from '@/app/(protected)/tests/components/TestSetSelectionDialog';
import { formatDate } from '@/utils/date';

interface LinkedTestSetsSectionProps {
  testId: string;
  sessionToken: string;
}

export default function LinkedTestSetsSection({
  testId,
  sessionToken,
}: LinkedTestSetsSectionProps) {
  const { show: showNotification } = useNotifications();

  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);

  const fetchLinkedTestSets = useCallback(async () => {
    if (!testId || !sessionToken) return;
    setLoading(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();
      const response = await testsClient.getLinkedTestSets(testId, {
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setTestSets(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch {
      showNotification('Failed to load linked test sets', {
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [
    testId,
    sessionToken,
    paginationModel.page,
    paginationModel.pageSize,
    showNotification,
  ]);

  useEffect(() => {
    fetchLinkedTestSets();
  }, [fetchLinkedTestSets]);

  const handleAssign = async (testSet: TestSet) => {
    try {
      const testSetsClient = new TestSetsClient(sessionToken);
      await testSetsClient.associateTestsWithTestSet(testSet.id, [testId]);
      showNotification(`Assigned to "${testSet.name}"`, {
        severity: 'success',
        autoHideDuration: 4000,
      });
      setAssignDialogOpen(false);
      await fetchLinkedTestSets();
    } catch (error) {
      const msg = error instanceof Error ? error.message : '';
      if (msg.includes('already associated')) {
        showNotification('Test is already assigned to this test set', {
          severity: 'warning',
        });
      } else {
        showNotification('Failed to assign to test set', { severity: 'error' });
      }
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      renderCell: params => (
        <Link
          href={`/test-sets/${params.row.id}`}
          style={{ color: 'inherit', textDecoration: 'underline' }}
          onClick={e => e.stopPropagation()}
        >
          {params.value}
        </Link>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      renderCell: params => (
        <Typography
          variant="body2"
          sx={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {params.value ?? '—'}
        </Typography>
      ),
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 200,
      renderCell: params => (
        <Typography variant="body2">
          {params.value ? formatDate(params.value) : '—'}
        </Typography>
      ),
    },
    {
      field: 'visibility',
      headerName: 'Visibility',
      width: 120,
      renderCell: params => (
        <GridBadge label={params.value ?? 'organization'} />
      ),
    },
    {
      field: '__actions',
      headerName: '',
      width: 80,
      sortable: false,
      renderCell: () => null,
    },
  ];

  const isEmpty = !loading && testSets.length === 0;

  return (
    <>
      {isEmpty ? (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <RouteOutlinedIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No assigned entity yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Assign this test to a test set to group related cases together.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setAssignDialogOpen(true)}
            >
              Assign entity
            </Button>
          </Box>
        </Paper>
      ) : (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 2,
            }}
          >
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              Linked entities ({totalCount})
            </Typography>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => setAssignDialogOpen(true)}
            >
              Assign
            </Button>
          </Box>

          <BaseDataGrid
            rows={testSets}
            columns={columns}
            loading={loading}
            disableRowSelectionOnClick
            pageSizeOptions={[5, 10, 25]}
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            getRowId={row => row.id}
            showToolbar={true}
            disablePaperWrapper={true}
            serverSidePagination={true}
            totalRows={totalCount}
          />
        </Paper>
      )}

      <TestSetSelectionDialog
        open={assignDialogOpen}
        onClose={() => setAssignDialogOpen(false)}
        onSelect={handleAssign}
        sessionToken={sessionToken}
      />
    </>
  );
}
