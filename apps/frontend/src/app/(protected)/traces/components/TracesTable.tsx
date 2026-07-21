'use client';

import React, { useContext, useMemo } from 'react';
import {
  GridColDef,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  TraceSummary,
  TRACE_METRICS_STATUS,
} from '@/utils/api-client/interfaces/telemetry';
import { Box, Stack, Tooltip, Typography } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import ForumIcon from '@mui/icons-material/Forum';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import { isPassedStatusName } from '@/utils/test-result-status';
import { formatDistanceToNowStrict } from 'date-fns';
import { formatDuration } from '@/utils/format-duration';
import { formatDate } from '@/utils/date';
import { TEST_TYPE_PILL_TABS } from '@/constants/test-types';
import TraceFilterDrawer, {
  type TraceDrawerFilters,
} from './TraceFilterDrawer';
import {
  hasActiveTraceDrawerFilters,
  countActiveTraceDrawerFilters,
} from './trace-filter-params';

const PILL_TABS = TEST_TYPE_PILL_TABS;

interface TracesToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  typeFilter: string;
  setTypeFilter: (v: string) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

const TracesToolbarContext = React.createContext<TracesToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function TracesUnifiedToolbar({
  hideTypeFilter,
}: {
  hideTypeFilter?: boolean;
}) {
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(TracesToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search operations…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        hideTypeFilter ? undefined : (
          <ToolbarPillTabs
            tabs={PILL_TABS}
            activeValue={typeFilter}
            onChange={setTypeFilter}
          />
        )
      }
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

interface TracesTableProps {
  traces: TraceSummary[];
  loading: boolean;
  onRowClick: (traceId: string, projectId: string) => void;
  totalCount: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  drawerFilters: TraceDrawerFilters;
  onApplyDrawerFilters: (filters: TraceDrawerFilters) => void;
  filterDrawerOpen: boolean;
  onFilterDrawerOpen: () => void;
  onFilterDrawerClose: () => void;
  fixedTestRunId?: string;
}

export default function TracesTable({
  traces,
  loading,
  onRowClick,
  totalCount,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  searchQuery,
  onSearchQueryChange,
  typeFilter,
  onTypeFilterChange,
  drawerFilters,
  onApplyDrawerFilters,
  filterDrawerOpen,
  onFilterDrawerOpen,
  onFilterDrawerClose,
  fixedTestRunId,
}: TracesTableProps) {
  const hasActiveDrawerFilters = hasActiveTraceDrawerFilters(drawerFilters, {
    testRunScope: Boolean(fixedTestRunId),
    excludeTestRunId: Boolean(fixedTestRunId),
  });
  const activeFilterCount = countActiveTraceDrawerFilters(drawerFilters, {
    testRunScope: Boolean(fixedTestRunId),
    excludeTestRunId: Boolean(fixedTestRunId),
  });

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'trace_id',
        headerName: 'Trace ID',
        width: 140,
        minWidth: 100,
        resizable: true,
        renderCell: params => {
          const traceId = params.value as string;
          const truncated = `${traceId.slice(0, 8)}\u2026`;
          const hasConversation = !!params.row.conversation_id;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {hasConversation ? (
                <Tooltip title="Multi-turn conversation">
                  <ForumIcon
                    fontSize="small"
                    sx={{ color: 'primary.main', flexShrink: 0 }}
                  />
                </Tooltip>
              ) : (
                <Tooltip title="Single-turn conversation">
                  <ChatBubbleOutlineIcon
                    fontSize="small"
                    sx={{ color: 'text.secondary', flexShrink: 0 }}
                  />
                </Tooltip>
              )}
              <Tooltip title={traceId}>
                <Typography
                  variant="body2"
                  sx={{ fontFamily: 'monospace', cursor: 'pointer' }}
                >
                  {truncated}
                </Typography>
              </Tooltip>
            </Box>
          );
        },
      },
      {
        field: 'root_operation',
        headerName: 'Operation',
        width: 240,
        minWidth: 120,
        resizable: true,
        renderCell: params => (
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {params.value}
          </Typography>
        ),
      },
      {
        field: 'conversation_input',
        headerName: 'Input',
        width: 320,
        minWidth: 160,
        resizable: true,
        renderCell: params => {
          const input = params.value as string | undefined;
          if (!input) {
            return (
              <Typography
                variant="body2"
                sx={{ color: 'text.disabled', fontStyle: 'italic' }}
              >
                —
              </Typography>
            );
          }
          return (
            <Tooltip title={input}>
              <Typography
                variant="body2"
                sx={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%',
                }}
              >
                {input}
              </Typography>
            </Tooltip>
          );
        },
      },
      {
        field: 'endpoint_name',
        headerName: 'Endpoint',
        width: 180,
        minWidth: 100,
        resizable: true,
        renderCell: params => {
          const endpointName = params.value as string | undefined;
          if (!endpointName) {
            return (
              <Typography
                variant="body2"
                sx={{ color: 'text.disabled', fontStyle: 'italic' }}
              >
                —
              </Typography>
            );
          }
          return (
            <Typography
              variant="body2"
              sx={{ overflow: 'hidden', textOverflow: 'ellipsis' }}
            >
              {endpointName}
            </Typography>
          );
        },
      },
      {
        field: 'start_time',
        headerName: 'Started',
        width: 150,
        minWidth: 100,
        resizable: true,
        renderCell: params => {
          const timeAgo = formatDistanceToNowStrict(new Date(params.value), {
            addSuffix: true,
          });
          return (
            <Tooltip title={formatDate(params.value)}>
              <Typography variant="body2">{timeAgo}</Typography>
            </Tooltip>
          );
        },
      },
      {
        field: 'duration_ms',
        headerName: 'Duration',
        width: 120,
        minWidth: 80,
        resizable: true,
        align: 'right',
        renderCell: params => {
          const ms = params.value as number;
          return <Typography variant="body2">{formatDuration(ms)}</Typography>;
        },
      },
      {
        field: 'span_count',
        headerName: 'Spans',
        width: 80,
        minWidth: 60,
        resizable: true,
        align: 'center',
      },
      {
        field: 'trace_metrics_status',
        headerName: 'Evaluation',
        width: 140,
        minWidth: 100,
        resizable: true,
        renderCell: params => {
          const evalStatus = params.value as string | undefined;
          const row = params.row as TraceSummary;
          const hasReview = row.has_reviews;
          const lastReview = row.last_review;

          if (!evalStatus) {
            return (
              <Typography
                variant="body2"
                sx={{ color: 'text.disabled', fontStyle: 'italic' }}
              >
                —
              </Typography>
            );
          }
          const reviewConflicts =
            hasReview &&
            lastReview?.status?.name &&
            isPassedStatusName(lastReview.status.name) !==
              (evalStatus === TRACE_METRICS_STATUS.PASS);

          return (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <GridBadge label={evalStatus} />
              {hasReview && (
                <Tooltip
                  title={
                    reviewConflicts
                      ? 'Human review conflicts with automation'
                      : 'Human reviewed'
                  }
                >
                  <RateReviewOutlinedIcon
                    fontSize="small"
                    sx={{
                      color: reviewConflicts
                        ? 'warning.main'
                        : 'text.secondary',
                      fontSize: 16,
                    }}
                  />
                </Tooltip>
              )}
            </Stack>
          );
        },
      },
      {
        field: 'environment',
        headerName: 'Environment',
        width: 120,
        minWidth: 90,
        resizable: true,
        renderCell: params => {
          const env = params.value as string;
          if (!env) return null;

          const envLabel = env.charAt(0).toUpperCase() + env.slice(1);
          return <GridBadge label={envLabel} />;
        },
      },
    ],
    []
  );

  const handleRowClick = (params: {
    row: { trace_id: string; project_id: string };
  }) => {
    onRowClick(params.row.trace_id, params.row.project_id);
  };

  const toolbarContextValue = useMemo(
    () => ({
      searchQuery,
      setSearchQuery: onSearchQueryChange,
      typeFilter,
      setTypeFilter: onTypeFilterChange,
      openFilterDrawer: onFilterDrawerOpen,
      hasActiveDrawerFilters,
      activeFilterCount,
    }),
    [
      searchQuery,
      onSearchQueryChange,
      typeFilter,
      onTypeFilterChange,
      onFilterDrawerOpen,
      hasActiveDrawerFilters,
      activeFilterCount,
    ]
  );

  return (
    <TracesToolbarContext.Provider value={toolbarContextValue}>
      <BaseDataGrid
        rows={traces}
        columns={columns}
        loading={loading}
        getRowId={row => row.trace_id}
        onRowClick={handleRowClick}
        serverSidePagination
        totalRows={totalCount}
        paginationModel={{ page, pageSize }}
        onPaginationModelChange={model => {
          if (model.page !== page) {
            onPageChange(model.page);
          }
          if (model.pageSize !== pageSize) {
            onPageSizeChange(model.pageSize);
          }
        }}
        pageSizeOptions={[25, 50, 100]}
        disablePaperWrapper
        showToolbar
        toolbarSlot={() => (
          <TracesUnifiedToolbar hideTypeFilter={Boolean(fixedTestRunId)} />
        )}
        persistState
        storageKey="traces-grid"
        sx={{
          '& .MuiDataGrid-row': {
            cursor: 'pointer',
          },
          '& .MuiDataGrid-cell': {
            borderBottom: 1,
            borderColor: 'divider',
          },
        }}
      />

      <TraceFilterDrawer
        open={filterDrawerOpen}
        onClose={onFilterDrawerClose}
        filters={drawerFilters}
        onApply={onApplyDrawerFilters}
        fixedTestRunId={fixedTestRunId}
      />
    </TracesToolbarContext.Provider>
  );
}
