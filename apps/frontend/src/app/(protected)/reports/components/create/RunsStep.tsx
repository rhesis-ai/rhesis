'use client';

import * as React from 'react';
import { Alert, Box, Stack, Typography } from '@mui/material';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import { format } from 'date-fns';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { versionLabel } from '@/components/reports/version';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

function passRate(run: TestRunDetail): string {
  const total = run.stats?.total ?? 0;
  if (!total) return '—';
  return `${Math.round(((run.stats?.passed ?? 0) * 1000) / total) / 10}%`;
}

const COLUMNS: GridColDef[] = [
  { field: 'name', headerName: 'Run', flex: 1.5 },
  {
    field: 'started_at',
    headerName: 'Started',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<TestRunDetail>) => {
      // The list response carries no created_at; the run stores when it started.
      const started = params.row.attributes?.started_at;
      return typeof started === 'string'
        ? format(new Date(started), 'dd/MM/yyyy HH:mm')
        : '—';
    },
  },
  {
    field: 'user',
    headerName: 'Run by',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<TestRunDetail>) =>
      params.row.user?.name || params.row.user?.email || '—',
  },
  {
    field: 'version',
    headerName: 'Version',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<TestRunDetail>) =>
      versionLabel(params.row.attributes?.version_info) ?? '—',
  },
  {
    field: 'pass_rate',
    headerName: 'Pass rate',
    width: 110,
    sortable: false,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params: GridRenderCellParams<TestRunDetail>) =>
      passRate(params.row),
  },
];

interface RunsStepProps {
  runs: TestRunDetail[];
  loading: boolean;
  selected: string[];
  onChange: (ids: string[]) => void;
}

export default function RunsStep({
  runs,
  loading,
  selected,
  onChange,
}: RunsStepProps) {
  const versions = new Set(
    runs
      .filter(run => selected.includes(run.id))
      .map(run => versionLabel(run.attributes?.version_info))
      .filter((label): label is string => Boolean(label))
  );

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Pick the runs on this endpoint that count for the report. When a test
        ran in more than one picked run, the result from the latest run counts.
      </Typography>
      {versions.size > 1 && (
        <Alert severity="warning">
          The picked runs report different endpoint versions:{' '}
          {[...versions].join(', ')}. Unpick some, or keep them on purpose.
        </Alert>
      )}
      {!loading && runs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          This endpoint has no test runs yet. Run a test set against it first.
        </Typography>
      ) : (
        <Box sx={{ width: '100%' }}>
          <BaseDataGrid
            rows={runs}
            columns={COLUMNS}
            loading={loading}
            getRowId={row => String(row.id)}
            checkboxSelection
            disableColumnResize
            rowSelectionModel={selected}
            onRowSelectionModelChange={(model: GridRowSelectionModel) =>
              onChange(model.map(String))
            }
            disablePaperWrapper
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: { paginationModel: { page: 0, pageSize: 10 } },
            }}
          />
        </Box>
      )}
    </Stack>
  );
}
