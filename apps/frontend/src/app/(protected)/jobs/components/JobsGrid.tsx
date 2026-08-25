'use client';

import * as React from 'react';
import { useCallback, useContext, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { Box, Chip, LinearProgress, Tooltip, Typography } from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';

import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import { useGridState } from '@/hooks/useGridState';
import { useGridQuery } from '@/hooks/useGridQuery';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { jobKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type { Job } from '@/utils/api-client/interfaces/job';
import {
  combineJobFiltersToOData,
  countActiveJobFilters,
  EMPTY_JOB_FILTERS,
  hasActiveJobFilters,
  type JobFilters,
} from '@/utils/odata-filter';
import { JOB_STATUS_COLOR, JOB_STATUS_LABEL } from '@/constants/jobs';
import { JobsIcon } from '@/components/icons';
import JobFilterDrawer from './JobFilterDrawer';

/**
 * Pill tabs are the coarse cut people actually want ("what is running", "what
 * broke"); everything finer lives in the drawer. 'active' is not a status the
 * backend has -- it expands to queued/running/cancelling below.
 */
const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Failed', value: 'failed' },
] as const;

const PILL_TO_FILTER: Record<string, JobFilters['status']> = {
  failed: 'failed',
};

interface JobsToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusPill: string;
  setStatusPill: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const JobsToolbarContext = React.createContext<JobsToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusPill: 'all',
  setStatusPill: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function JobsUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusPill,
    setStatusPill,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(JobsToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search jobs…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={[...STATUS_PILL_TABS]}
          activeValue={statusPill}
          onChange={setStatusPill}
        />
      }
    />
  );
}

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

export default function JobsGrid() {
  const router = useRouter();
  const { status: sessionStatus } = useSession();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusPill, setStatusPill] = useState('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<JobFilters>(EMPTY_JOB_FILTERS);

  const {
    paginationModel,
    sortModel,
    handlePaginationModelChange,
    handleSortModelChange,
  } = useGridState({ initialPageSize: 25 });

  /**
   * The pill narrows the drawer's status rather than fighting it: a user who
   * picked "failed" in the drawer and then clicks the Active pill should see
   * active jobs, so the pill wins for the one field they overlap on.
   */
  const effectiveFilters = useMemo<JobFilters>(() => {
    if (statusPill === 'all') return drawerFilters;
    return { ...drawerFilters, status: PILL_TO_FILTER[statusPill] ?? '' };
  }, [drawerFilters, statusPill]);

  const filterString = useMemo(() => {
    const base = combineJobFiltersToOData(searchQuery, effectiveFilters);
    if (statusPill !== 'active') return base;

    // 'active' is the complement of the terminal states. Expressed as a status
    // list rather than "not terminal" because OData has no notion of which of
    // our statuses are terminal.
    const activeClause =
      "(status eq 'queued' or status eq 'running' or status eq 'cancelling')";
    return base ? `(${base}) and ${activeClause}` : activeClause;
  }, [searchQuery, effectiveFilters, statusPill]);

  const LIVE_POLL_MS = 3000;

  const {
    data: jobsData,
    isLoading: loading,
    errorMessage: error,
  } = useGridQuery({
    queryKey: jobKeys.list(
      filterString ?? '',
      paginationModel.page,
      paginationModel.pageSize,
      sortModel[0]?.field ?? 'created_at',
      sortModel[0]?.sort ?? 'desc'
    ),
    errorFallbackMessage: 'Failed to load jobs',
    enabled: isAuthenticated(sessionStatus),
    staleTime: 0,
    queryFn: () => {
      const client = new ApiClientFactory().getJobsClient();
      return client.getJobs({
        skip: paginationModel.page * paginationModel.pageSize,
        limit: paginationModel.pageSize,
        sort_by: sortModel[0]?.field ?? 'created_at',
        sort_order: sortModel[0]?.sort ?? 'desc',
        $filter: filterString,
      });
    },
    refetchInterval: query =>
      query.state.data?.data.some(j => !j.is_terminal) ? LIVE_POLL_MS : false,
  });

  const jobs = jobsData?.data ?? [];
  const totalCount = jobsData?.totalCount ?? 0;

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

  const toolbarState = useMemo<JobsToolbarState>(
    () => ({
      searchQuery,
      setSearchQuery,
      statusPill,
      setStatusPill,
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters: hasActiveJobFilters(drawerFilters),
      activeFilterCount: countActiveJobFilters(drawerFilters),
    }),
    [searchQuery, statusPill, drawerFilters]
  );

  const handleRowClick = useCallback(
    (jobId: string) => router.push(`/jobs/${jobId}`),
    [router]
  );

  const isFiltered =
    searchQuery !== '' ||
    statusPill !== 'all' ||
    hasActiveJobFilters(drawerFilters);

  return (
    <JobsToolbarContext.Provider value={toolbarState}>
      <GridStateGate
        data={jobsData}
        error={error}
        isEmpty={jobs.length === 0 && !isFiltered}
        emptyState={
          <EntityEmptyState
            icon={JobsIcon}
            title="No jobs yet"
            description="Background work shows up here when you generate a test set, run tests, or import from Garak."
          />
        }
      >
        <BaseDataGrid
          rows={jobs}
          columns={columns}
          getRowId={row => String(row.id)}
          loading={loading}
          serverSidePagination
          totalRows={totalCount}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          sortModel={sortModel}
          onSortModelChange={handleSortModelChange}
          pageSizeOptions={[10, 25, 50, 100]}
          toolbarSlot={JobsUnifiedToolbar}
          onRowClick={params => handleRowClick(String(params.id))}
          persistState
        />
      </GridStateGate>

      <JobFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={setDrawerFilters}
      />
    </JobsToolbarContext.Provider>
  );
}
