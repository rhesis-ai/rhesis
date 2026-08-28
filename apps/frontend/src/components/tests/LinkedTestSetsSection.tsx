'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RouteOutlinedIcon from '@mui/icons-material/RouteOutlined';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import { GridColDef, GridRowModel } from '@mui/x-data-grid';
import { TestSetsClient } from '@/utils/api-client/test-sets-client';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';
import { useList } from '@/hooks/useList';
import { linkedTestSetsList } from './list';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

const NO_FILTERS = {};

interface LinkedTestSetsSectionProps {
  testId: string;
  /** Server-prefetched first page; undefined falls back to a client fetch. */
  initialTestSets?: TestSet[];
  initialTotalCount?: number;
}

export default function LinkedTestSetsSection({
  testId,
  initialTestSets,
  initialTotalCount,
}: LinkedTestSetsSectionProps) {
  const { show: showNotification } = useNotifications();
  const canEditTest = useCan(Capability.TestSet.UPDATE);

  // Assign drawer state
  const [assignOpen, setAssignOpen] = useState(false);
  const [available, setAvailable] = useState<TestSet[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);

  const descriptor = useMemo(() => linkedTestSetsList(testId), [testId]);
  const {
    data: testSets,
    totalCount,
    isLoading: loading,
    refresh: fetchLinkedTestSets,
    paginationModel,
    onPaginationModelChange: setPaginationModel,
  } = useList(descriptor, {
    filters: NO_FILTERS,
    enabled: !!testId,
    initialData: initialTestSets,
    initialTotalCount,
    onError: () =>
      showNotification('Failed to load linked test sets', {
        severity: 'error',
      }),
  });

  const handleAssignClick = useCallback(async () => {
    setLoadingAvailable(true);
    setAssignOpen(true);
    try {
      const testSetsClient = new TestSetsClient();
      const response = await testSetsClient.getTestSets({
        limit: 100,
        sort_by: 'name',
        sort_order: 'asc',
      });
      setAvailable(response.data);
    } catch {
      setAvailable([]);
      showNotification('Failed to load test sets', { severity: 'error' });
    } finally {
      setLoadingAvailable(false);
    }
  }, [showNotification]);

  const linkedIds = useMemo(
    () => new Set(testSets.map(ts => String(ts.id))),
    [testSets]
  );

  const availableFiltered = useMemo<GridRowModel[]>(
    () => available.filter(ts => !linkedIds.has(String(ts.id))),
    [available, linkedIds]
  );

  const handleAssign = useCallback(
    async (selectedIds: string[]) => {
      const testSetsClient = new TestSetsClient();
      const errors: string[] = [];
      await Promise.all(
        selectedIds.map(async id => {
          try {
            await testSetsClient.associateTestsWithTestSet(id, [testId]);
          } catch (error) {
            const msg = error instanceof Error ? error.message : '';
            if (!msg.includes('already associated')) {
              errors.push(id);
            }
          }
        })
      );
      if (errors.length > 0) {
        showNotification('Failed to assign to some test sets', {
          severity: 'error',
        });
      } else {
        showNotification(
          `Assigned to ${selectedIds.length} test set${selectedIds.length !== 1 ? 's' : ''}`,
          { severity: 'success', autoHideDuration: 4000 }
        );
      }
      setAssignOpen(false);
      fetchLinkedTestSets();
    },
    [testId, showNotification, fetchLinkedTestSets]
  );

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
      flex: 2,
      renderCell: params => (
        <Typography variant="body2">
          {params.value ? formatDate(params.value) : '—'}
        </Typography>
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

  const drawerColumns: GridColDef[] = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
    { field: 'description', headerName: 'Description', flex: 2, minWidth: 200 },
  ];

  const isEmpty = !loading && testSets.length === 0;

  return (
    <>
      {isEmpty ? (
        <Paper
          elevation={0}
          sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 2 }}
        >
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
              No test sets assigned yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {canEditTest
                ? 'Assign this test to a test set to group related cases together.'
                : 'This test has no linked test sets yet.'}
            </Typography>
            {canEditTest && (
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleAssignClick}
              >
                Assign to test set
              </Button>
            )}
          </Box>
        </Paper>
      ) : (
        <Paper
          elevation={0}
          sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 2 }}
        >
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
              Linked Test Sets ({totalCount})
            </Typography>
            {canEditTest && (
              <Button
                variant="outlined"
                startIcon={<AddIcon />}
                onClick={handleAssignClick}
              >
                Assign
              </Button>
            )}
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
            disablePaperWrapper={true}
            serverSidePagination={true}
            totalRows={totalCount}
          />
        </Paper>
      )}

      {canEditTest && (
        <AssignEntityDrawer
          open={assignOpen}
          onClose={() => setAssignOpen(false)}
          title="Assign Test Set"
          rows={availableFiltered}
          columns={drawerColumns}
          loading={loadingAvailable}
          getRowId={row => String(row.id)}
          onAssign={handleAssign}
          searchPlaceholder="Search test sets…"
        />
      )}
    </>
  );
}
