'use client';

import * as React from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type {
  GridColDef,
  GridRenderCellParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import { format } from 'date-fns';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import RunStatusChip from '@/components/reports/RunStatusChip';
import { formatPassRate } from '@/components/reports/ReportSection';
import { PAGE_LIMIT } from '@/components/reports/picker/useReportPickerData';
import { runExperimentLabel } from '@/components/reports/experiment';
import { versionLabel } from '@/components/reports/version';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

export type RunSource = 'tag' | 'manual';

export const RUN_SOURCES: Record<
  RunSource,
  { label: string; description: string }
> = {
  manual: {
    label: 'By hand',
    description: 'You tick the runs. Only those count.',
  },
  tag: {
    label: 'By tag',
    description:
      'Every run with a tag you name. Runs tagged later join until you publish.',
  },
};

type Params = GridRenderCellParams<TestRunDetail>;

function passRate(run: TestRunDetail): string {
  const total = run.stats?.total ?? 0;
  return formatPassRate(
    total ? ((run.stats?.passed ?? 0) * 100) / total : null
  );
}

const EXPERIMENT_COLUMN: GridColDef = {
  field: 'experiment',
  headerName: 'Experiment',
  flex: 1.5,
  sortable: false,
  renderCell: (params: Params) => runExperimentLabel(params.row) ?? '—',
};

const COLUMNS: GridColDef[] = [
  { field: 'name', headerName: 'Run', flex: 1.5 },
  {
    field: 'test_set',
    headerName: 'Test set',
    flex: 2,
    sortable: false,
    renderCell: (params: Params) =>
      params.row.test_configuration?.test_set?.name ?? '—',
  },
  EXPERIMENT_COLUMN,
  {
    field: 'status',
    headerName: 'Status',
    flex: 1,
    sortable: false,
    renderCell: (params: Params) => (
      <RunStatusChip status={params.row.status?.name} />
    ),
  },
  {
    field: 'started_at',
    headerName: 'Started',
    flex: 1,
    sortable: false,
    renderCell: (params: Params) => {
      // The list response carries no created_at; the run stores when it started.
      const started = params.row.attributes?.started_at;
      return typeof started === 'string'
        ? format(new Date(started), 'dd/MM/yyyy HH:mm')
        : '—';
    },
  },
  {
    field: 'pass_rate',
    headerName: 'Pass rate',
    width: 110,
    sortable: false,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params: Params) => passRate(params.row),
  },
];

/** Runs whose tags include ``tag`` (case-insensitive). */
export function runsWithTag(runs: TestRunDetail[], tag: string): string[] {
  const wanted = tag.trim().toLowerCase();
  if (!wanted) return [];
  return runs
    .filter(run => (run.tags ?? []).some(t => t.name.toLowerCase() === wanted))
    .map(run => String(run.id));
}

export function RunSourceSelect({
  value,
  onChange,
}: {
  value: RunSource;
  onChange: (source: RunSource) => void;
}) {
  return (
    <TextField
      select
      label="How should runs be picked?"
      value={value}
      onChange={e => onChange(e.target.value as RunSource)}
      helperText={RUN_SOURCES[value].description}
      fullWidth
    >
      {Object.entries(RUN_SOURCES).map(([key, { label }]) => (
        <MenuItem key={key} value={key}>
          {label}
        </MenuItem>
      ))}
    </TextField>
  );
}

interface RunsStepProps {
  source: RunSource;
  runs: TestRunDetail[];
  loading: boolean;
  /** Hand-picked runs; used when ``source`` is manual. */
  selected: string[];
  onChange: (ids: string[]) => void;
  /** Used when ``source`` is tag. */
  tag: string;
  onTagChange: (tag: string) => void;
  /** The endpoint has more runs than were loaded. */
  truncated?: boolean;
}

export default function RunsStep({
  source,
  runs,
  loading,
  selected,
  onChange,
  tag,
  onTagChange,
  truncated = false,
}: RunsStepProps) {
  const tagged = React.useMemo(() => runsWithTag(runs, tag), [runs, tag]);
  const tagOptions = React.useMemo(
    () =>
      [
        ...new Set(runs.flatMap(run => (run.tags ?? []).map(t => t.name))),
      ].sort(),
    [runs]
  );
  const included = source === 'tag' ? tagged : selected;
  const versions = new Set(
    runs
      .filter(run => included.includes(String(run.id)))
      .map(run => versionLabel(run.attributes?.version_info))
      .filter((label): label is string => Boolean(label))
  );
  const rows =
    source === 'tag'
      ? runs.filter(run => tagged.includes(String(run.id)))
      : runs;

  const withExperiment = runs.some(run => run.experiment_id);
  const columns = React.useMemo(
    () => COLUMNS.filter(c => withExperiment || c !== EXPERIMENT_COLUMN),
    [withExperiment]
  );
  const setups = new Set(
    runs
      .filter(run => included.includes(String(run.id)))
      .map(run => runExperimentLabel(run) ?? 'no experiment')
  );
  const mixedSetups = withExperiment && setups.size > 1;

  const grid = (
    <Box sx={{ width: '100%' }}>
      <BaseDataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        getRowId={row => String(row.id)}
        disableColumnResize
        disablePaperWrapper
        pageSizeOptions={[10, 25, 50]}
        initialState={{
          pagination: { paginationModel: { page: 0, pageSize: 10 } },
        }}
        {...(source === 'manual'
          ? {
              checkboxSelection: true,
              keepNonExistentRowsSelected: true,
              rowSelectionModel: selected,
              onRowSelectionModelChange: (model: GridRowSelectionModel) =>
                onChange(model.map(String)),
            }
          : {})}
      />
    </Box>
  );

  if (!loading && runs.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        This endpoint has no test runs yet. Run a test set against it first.
      </Typography>
    );
  }

  return (
    <Stack spacing={2}>
      {source === 'tag' && (
        <Autocomplete
          freeSolo
          options={tagOptions}
          // Bind only the text: binding `value` too stops MUI filtering as you type.
          inputValue={tag}
          onInputChange={(_event, value) => onTagChange(value)}
          renderInput={params => (
            <TextField
              {...params}
              label="Tag"
              placeholder="e.g. 2.5"
              required
              helperText={
                tag.trim()
                  ? `${tagged.length} run${tagged.length === 1 ? '' : 's'} with this tag so far. Runs tagged later join until you publish.`
                  : 'Runs with this tag join automatically until you publish.'
              }
            />
          )}
        />
      )}
      {mixedSetups && (
        <Alert severity="warning">
          These runs used different setups: {[...setups].join(', ')}. The
          numbers will mix them.
        </Alert>
      )}
      {versions.size > 1 && (
        <Alert severity="warning">
          These runs report different endpoint versions:{' '}
          {[...versions].join(', ')}.
          {source === 'manual' ? ' Unpick some, or keep them on purpose.' : ''}
        </Alert>
      )}
      {source === 'manual' || tag.trim() ? grid : null}
      {truncated && (
        <Typography variant="caption" color="text.secondary">
          {source === 'manual'
            ? `Showing the ${PAGE_LIMIT} newest runs. Older runs you picked before stay in the report.`
            : `Only the ${PAGE_LIMIT} newest runs were checked for this tag here; the report itself includes every tagged run.`}
        </Typography>
      )}
    </Stack>
  );
}
