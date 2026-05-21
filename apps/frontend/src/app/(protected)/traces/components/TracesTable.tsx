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
import {
  Box,
  Button,
  ButtonGroup,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import BadgeChip from '@/components/common/BadgeChip';
import ForumIcon from '@mui/icons-material/Forum';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import { isPassedStatusName } from '@/utils/test-result-status';
import { formatDistanceToNowStrict } from 'date-fns';
import { formatDuration } from '@/utils/format-duration';
import { SearchPill } from '@/components/common/SearchPill';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';
import TraceFilterDrawer, {
  type TraceDrawerFilters,
} from './TraceFilterDrawer';
import { hasActiveTraceDrawerFilters } from './trace-filter-params';

const PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Single Turn', value: 'single_turn' },
  { label: 'Multi Turn', value: 'multi_turn' },
];

interface TracesToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  typeFilter: string;
  setTypeFilter: (v: string) => void;
  openFilterDrawer: () => void;
  onRefresh: () => void;
  hasActiveDrawerFilters: boolean;
}

const TracesToolbarContext = React.createContext<TracesToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  typeFilter: 'all',
  setTypeFilter: () => {},
  openFilterDrawer: () => {},
  onRefresh: () => {},
  hasActiveDrawerFilters: false,
});

function TracesUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    typeFilter,
    setTypeFilter,
    openFilterDrawer,
    onRefresh,
    hasActiveDrawerFilters,
  } = useContext(TracesToolbarContext);

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
        minHeight: 52,
      }}
    >
      <Tooltip title="Filters">
        <IconButton
          size="small"
          onClick={openFilterDrawer}
          aria-label="Filters"
          sx={{
            position: 'relative',
            bgcolor: 'primary.main',
            color: '#fff',
            borderRadius: BORDER_RADIUS.sm,
            width: 36,
            height: 36,
            flexShrink: 0,
            '&:hover': { bgcolor: 'primary.dark' },
          }}
        >
          <TuneOutlinedIcon sx={{ fontSize: 20 }} />
          {hasActiveDrawerFilters && (
            <Box
              sx={{
                position: 'absolute',
                top: 4,
                right: 4,
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: 'warning.light',
                border: '2px solid',
                borderColor: 'primary.main',
                pointerEvents: 'none',
              }}
            />
          )}
        </IconButton>
      </Tooltip>

      <SearchPill
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search operations…"
        width={240}
      />

      <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
        <ButtonGroup
          variant="outlined"
          size="small"
          sx={{
            '& .MuiButtonGroup-grouped': {
              borderRadius: 0,
              '&:first-of-type': {
                borderTopLeftRadius: BORDER_RADIUS.pill,
                borderBottomLeftRadius: BORDER_RADIUS.pill,
              },
              '&:last-of-type': {
                borderTopRightRadius: BORDER_RADIUS.pill,
                borderBottomRightRadius: BORDER_RADIUS.pill,
              },
              borderColor: theme =>
                theme.palette.mode === 'light'
                  ? GREYSCALE.light.border
                  : GREYSCALE.dark.border,
            },
          }}
        >
          {PILL_TABS.map(tab => (
            <Button
              key={tab.value}
              onClick={() => setTypeFilter(tab.value)}
              sx={{
                px: 2,
                py: 0.5,
                fontWeight: typeFilter === tab.value ? 600 : 400,
                bgcolor:
                  typeFilter === tab.value ? 'primary.dark' : 'transparent',
                color:
                  typeFilter === tab.value
                    ? '#fff'
                    : theme =>
                        theme.palette.mode === 'light'
                          ? GREYSCALE.light.body
                          : GREYSCALE.dark.body,
                '&:hover': {
                  bgcolor:
                    typeFilter === tab.value
                      ? 'primary.dark'
                      : theme =>
                          theme.palette.mode === 'light'
                            ? GREYSCALE.light.surface1
                            : GREYSCALE.dark.surface1,
                },
              }}
            >
              {tab.label}
            </Button>
          ))}
        </ButtonGroup>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={onRefresh} aria-label="Refresh">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <GridToolbarColumnsButton />
        <GridToolbarDensitySelector />
        <GridToolbarExport />
      </Box>
    </Box>
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
  onRefresh: () => void;
  sessionToken: string;
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
  onRefresh,
  sessionToken,
}: TracesTableProps) {
  const hasActiveDrawerFilters = hasActiveTraceDrawerFilters(drawerFilters);

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
        width: 300,
        minWidth: 120,
        resizable: true,
        renderCell: params => (
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {params.value}
          </Typography>
        ),
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
            <Tooltip title={new Date(params.value).toLocaleString()}>
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
              <BadgeChip label={evalStatus} />
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
          return <BadgeChip label={envLabel} />;
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
      onRefresh,
      hasActiveDrawerFilters,
    }),
    [
      searchQuery,
      onSearchQueryChange,
      typeFilter,
      onTypeFilterChange,
      onFilterDrawerOpen,
      onRefresh,
      hasActiveDrawerFilters,
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
        toolbarSlot={TracesUnifiedToolbar}
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
        sessionToken={sessionToken}
      />
    </TracesToolbarContext.Provider>
  );
}
