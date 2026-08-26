'use client';

import * as React from 'react';
import { useCallback, useMemo } from 'react';
import { Box, Chip, LinearProgress, Tooltip, Typography } from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';

import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { jobsList } from './list';
import type { Job } from '@/utils/api-client/interfaces/job';
import {
  countActiveJobFilters,
  EMPTY_JOB_FILTERS,
  type JobFilters,
} from '@/utils/odata-filter';
import { JOB_STATUS_COLOR, JOB_STATUS_LABEL } from '@/constants/jobs';
import { JobsIcon } from '@/components/icons';
import JobFilterDrawer from './JobFilterDrawer';

/**
 * Pill tabs are the coarse cut people actually want ("what is running", "what
 * broke"); everything finer lives in the drawer. 'active' is not a status the
 * backend has -- the descriptor's statusPill filter expands it.
 */
const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Failed', value: 'failed' },
];

const LIVE_POLL_MS = 3000;

/**
 * The pill narrows the drawer's status rather than fighting it: a user who
 * picked "failed" in the drawer and then clicks the Active pill should see
 * active jobs, so the pill wins for the one field they overlap on.
 */
function toFilters(state: EntityGridFilterState<JobFilters>) {
  return {
    search: state.search,
    status:
      state.pill === ''
        ? state.drawer.status
        : state.pill === 'failed'
          ? ('failed' as const)
          : ('' as const),
    statusPill: state.pill === 'active' ? 'active' : '',
    jobType: state.drawer.jobType,
    triggeredBy: state.drawer.triggeredBy,
    createdFrom: state.drawer.createdFrom,
    createdTo: state.drawer.createdTo,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<JobFilters> = {
  empty: EMPTY_JOB_FILTERS,
  countActive: countActiveJobFilters,
  render: props => (
    <JobFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

function StatusCell({ job }: { job: Job }) {
  const status = job.status as keyof typeof JOB_STATUS_COLOR;
  const chip = (
    <Chip
      size="small"
      label={JOB_STATUS_LABEL[status] ?? job.status}
      color={JOB_STATUS_COLOR[status] ?? 'default'}
    />
  );

  // Only failures carry a reason worth surfacing, and the message can be long,
  // so it goes in a tooltip rather than the cell.
  if (job.status === 'failed' && job.error_message) {
    return <Tooltip title={job.error_message}>{chip}</Tooltip>;
  }
  return chip;
}

function ProgressCell({ job }: { job: Job }) {
  const { progress_current: current, progress_total: total } = job;

  if (current === undefined || current === null) {
    return (
      <Typography variant="body2" color="text.secondary">
        —
      </Typography>
    );
  }

  if (!total) {
    return <Typography variant="body2">{current}</Typography>;
  }

  const pct = Math.min(100, Math.round((current / total) * 100));
  const done = current >= total;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
      {!done && (
        <LinearProgress
          variant="determinate"
          value={pct}
          sx={theme => ({
            flex: 1,
            height: theme.spacing(0.75),
            borderRadius: theme.shape.borderRadius,
            bgcolor: 'action.hover',
            '& .MuiLinearProgress-bar': {
              borderRadius: theme.shape.borderRadius,
            },
          })}
        />
      )}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ whiteSpace: 'nowrap' }}
      >
        {current}/{total}
      </Typography>
    </Box>
  );
}

function formatDuration(job: Job): string {
  const start = job.started_at ?? job.queued_at ?? job.created_at;
  const end = job.finished_at;
  if (!start || !end) return '—';

  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (Number.isNaN(ms) || ms < 0) return '—';

  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

interface JobsGridProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Job[];
  initialTotalCount?: number;
}

export default function JobsGrid({
  initialData,
  initialTotalCount,
}: JobsGridProps) {
  const getRowUrl = useCallback((row: Job) => `/jobs/${row.id}`, []);
  const pollMs = useCallback(
    (data: Job[]) => (data.some(j => !j.is_terminal) ? LIVE_POLL_MS : false),
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Job',
        flex: 2,
        minWidth: 200,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <Typography variant="body2">
            {params.row.name || params.row.job_type}
          </Typography>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        flex: 1,
        minWidth: 120,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <StatusCell job={params.row} />
        ),
      },
      {
        field: 'progress',
        headerName: 'Progress',
        flex: 1,
        minWidth: 120,
        sortable: false,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <ProgressCell job={params.row} />
        ),
      },
      {
        field: 'duration',
        headerName: 'Duration',
        flex: 0.8,
        minWidth: 100,
        sortable: false,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <Typography variant="body2">{formatDuration(params.row)}</Typography>
        ),
      },
      {
        field: 'user_display_name',
        headerName: 'Started by',
        flex: 1,
        minWidth: 120,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <Typography variant="body2" color="text.secondary">
            {params.row.user_display_name ?? '—'}
          </Typography>
        ),
      },
      {
        field: 'created_at',
        headerName: 'Started',
        flex: 1,
        minWidth: 160,
        renderCell: (params: GridRenderCellParams<Job>) => (
          <Typography variant="body2">
            {new Date(
              params.row.started_at ?? params.row.created_at
            ).toLocaleString()}
          </Typography>
        ),
      },
    ],
    []
  );

  return (
    <EntityGrid<Job, typeof jobsList.filters, JobFilters>
      descriptor={jobsList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          icon={JobsIcon}
          title="No jobs yet"
          description="Background work shows up here when you generate a test set, run tests, or import from Garak."
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      pollMs={pollMs}
      searchPlaceholder="Search jobs…"
      pills={{ tabs: STATUS_PILL_TABS }}
      drawer={drawerAdapter}
      getRowUrl={getRowUrl}
      showGridButtons={false}
      pageSizeOptions={[10, 25, 50, 100]}
      editAction={false}
    />
  );
}
