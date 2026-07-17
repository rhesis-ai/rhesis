'use client';

import * as React from 'react';
import { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  Grid,
  Stack,
  Typography,
} from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowParams,
} from '@mui/x-data-grid';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import BaseDrawer from '@/components/common/BaseDrawer';
import GridToolbar from '@/components/common/GridToolbar';
import SectionCard from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';
import { ArrowOutwardIcon, PlayArrowIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useQuery } from '@tanstack/react-query';
import { experimentKeys } from '@/constants/query-keys';
import {
  ExperimentResultsRunItem,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { BORDER_RADIUS } from '@/styles/theme';
import { formatDate } from '@/utils/date';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface ExperimentRunsTabProps {
  experimentId: string;
  onRunExperiment?: () => void;
}

export default function ExperimentRunsTab({
  experimentId,
  onRunExperiment,
}: ExperimentRunsTabProps) {
  const { status } = useSession();
  const [drawerRun, setDrawerRun] = useState<ExperimentResultsRunItem | null>(
    null
  );
  const [searchQuery, setSearchQuery] = useState('');

  const apiFactory = useMemo(() => new ApiClientFactory(), []);

  const {
    data,
    isLoading: loading,
    error: fetchError,
  } = useQuery({
    queryKey: [...experimentKeys.detail(experimentId), 'runs'],
    queryFn: () =>
      apiFactory.getParametersClient().getExperimentResultsByRun(experimentId),
    enabled: isAuthenticated(status) && !!experimentId,
  });

  const runs = data?.items ?? [];
  const error =
    fetchError instanceof Error
      ? fetchError.message
      : fetchError
        ? 'Failed to load runs'
        : null;

  const columns: GridColDef<ExperimentResultsRunItem>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Run',
        flex: 1.2,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography
              variant="body2"
              color="primary"
              sx={{
                '&:hover': { textDecoration: 'underline' },
                cursor: 'pointer',
              }}
            >
              {params.row.name || params.row.id.substring(0, 8)}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 1,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" color="text.secondary">
              {formatDate(params.row.created_at)}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'test_set',
        headerName: 'Test Set',
        flex: 1.2,
        sortable: false,
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.test_configuration?.test_set?.name ?? '',
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const testSet = params.row.test_configuration?.test_set;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography variant="body2" color="text.secondary" noWrap>
                {testSet?.name ?? '—'}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'version',
        headerName: 'Version',
        flex: 0.6,
        sortable: false,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {shortVersion(
                typeof params.row.attributes?.parameter_version === 'string'
                  ? params.row.attributes.parameter_version
                  : undefined
              )}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'total',
        headerName: 'Tests',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.total ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2">
              {params.row.stats?.total ?? 0}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'passed',
        headerName: 'Passed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.passed ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const passed = params.row.stats?.passed ?? 0;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography
                variant="body2"
                sx={{ color: passed > 0 ? 'success.main' : 'inherit' }}
              >
                {passed}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'failed',
        headerName: 'Failed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.failed ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const failed = params.row.stats?.failed ?? 0;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography
                variant="body2"
                sx={{ color: failed > 0 ? 'error.main' : 'inherit' }}
              >
                {failed}
              </Typography>
            </Box>
          );
        },
      },
    ],
    []
  );

  const title =
    !loading && runs.length > 0
      ? `Experiment Runs (${runs.length})`
      : undefined;

  const filteredRuns = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return runs;
    return runs.filter(
      r =>
        (r.name ?? '').toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q) ||
        (r.test_configuration?.test_set?.name ?? '').toLowerCase().includes(q)
    );
  }, [runs, searchQuery]);

  return (
    <>
      <SectionCard title={title}>
        {loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 4 }}>
            <CircularProgress size={20} />
            <Typography color="text.secondary">Loading runs...</Typography>
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : runs.length === 0 ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '20px',
              px: { xs: '24px', md: '200px' },
              py: '10px',
            }}
          >
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              <PlayArrowIcon sx={{ fontSize: 32, color: 'primary.main' }} />
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 600,
                  color: 'primary.main',
                  whiteSpace: 'nowrap',
                }}
              >
                No experiment runs yet
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ textAlign: 'center' }}>
              Run this experiment against a test set to compare versions and see
              evaluation results here.
            </Typography>
            {onRunExperiment && (
              <Button
                variant="contained"
                size="large"
                startIcon={<PlayArrowIcon />}
                onClick={onRunExperiment}
                sx={{
                  borderRadius: BORDER_RADIUS.md,
                  px: '20px',
                  py: '12px',
                  fontSize: 18,
                  fontWeight: 700,
                }}
              >
                Run experiment
              </Button>
            )}
          </Box>
        ) : (
          <>
            <GridToolbar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search runs…"
              sx={{ px: 0, pt: 0, pb: '24px' }}
            />
            {filteredRuns.length === 0 ? (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ py: 4, textAlign: 'center' }}
              >
                No runs match your search.
              </Typography>
            ) : (
              <BaseDataGrid
                rows={filteredRuns}
                columns={columns}
                getRowId={row => row.id}
                disableRowSelectionOnClick
                onRowClick={(params: GridRowParams<ExperimentResultsRunItem>) =>
                  setDrawerRun(params.row)
                }
                hideFooter={filteredRuns.length <= 25}
                disablePaperWrapper
                sx={{ cursor: 'pointer' }}
              />
            )}
          </>
        )}
      </SectionCard>

      <BaseDrawer
        open={!!drawerRun}
        onClose={() => setDrawerRun(null)}
        title={drawerRun?.name || drawerRun?.id?.substring(0, 8) || 'Run'}
        showHeader
        width={560}
        saveButtonText=""
        closeButtonText=""
      >
        {drawerRun && (
          <RunSummaryContent
            run={drawerRun}
            onClose={() => setDrawerRun(null)}
          />
        )}
      </BaseDrawer>
    </>
  );
}

function RunSummaryContent({
  run,
  onClose,
}: {
  run: ExperimentResultsRunItem;
  onClose: () => void;
}) {
  const total = run.stats?.total ?? 0;
  const passed = run.stats?.passed ?? 0;
  const failed = run.stats?.failed ?? 0;
  const errors = run.stats?.errors ?? 0;
  const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : null;
  const version =
    typeof run.attributes?.parameter_version === 'string'
      ? run.attributes.parameter_version
      : undefined;

  return (
    <Stack spacing={3}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 6 }}>
          <ViewField label="Tests" value={String(total)} />
        </Grid>
        <Grid size={{ xs: 6 }}>
          <ViewField
            label="Pass Rate"
            value={passRate !== null ? `${passRate}%` : '—'}
          />
        </Grid>
        <Grid size={{ xs: 4 }}>
          <ViewField label="Passed" value={String(passed)} />
        </Grid>
        <Grid size={{ xs: 4 }}>
          <ViewField label="Failed" value={String(failed)} />
        </Grid>
        <Grid size={{ xs: 4 }}>
          <ViewField label="Errors" value={String(errors)} />
        </Grid>
      </Grid>

      <Divider />

      <Grid container spacing={2}>
        {version && (
          <Grid size={12}>
            <ViewField label="Version" value={shortVersion(version)} />
          </Grid>
        )}
        {run.test_configuration?.test_set?.name && (
          <Grid size={12}>
            <ViewField
              label="Test Set"
              value={run.test_configuration.test_set.name}
            />
          </Grid>
        )}
        {run.created_at && (
          <Grid size={12}>
            <ViewField label="Created" value={formatDate(run.created_at)} />
          </Grid>
        )}
      </Grid>

      <Divider />

      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          component={Link}
          href={`/test-runs/${run.id}`}
          variant="contained"
          endIcon={<ArrowOutwardIcon fontSize="small" />}
          sx={{ flex: 1 }}
        >
          Go to Test Run
        </Button>
        <Button variant="outlined" onClick={onClose}>
          Close
        </Button>
      </Box>
    </Stack>
  );
}
