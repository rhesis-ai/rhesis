'use client';

import { useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import {
  TraceSummary,
  TRACE_METRICS_STATUS,
} from '@/utils/api-client/interfaces/telemetry';
import { Box, Chip, Stack, Typography, Tooltip } from '@mui/material';
import ForumIcon from '@mui/icons-material/Forum';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import { isPassedStatusName } from '@/utils/test-result-status';
import { formatDistanceToNowStrict } from 'date-fns';
import { formatDuration } from '@/utils/format-duration';

interface TracesTableProps {
  traces: TraceSummary[];
  loading: boolean;
  onRowClick: (traceId: string, projectId: string) => void;
  totalCount: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
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
}: TracesTableProps) {
  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'trace_id',
        headerName: 'Trace ID',
        width: 140,
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
        flex: 1,
        minWidth: 200,
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
        align: 'center',
      },
      {
        field: 'trace_metrics_status',
        headerName: 'Evaluation',
        width: 140,
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
          const color =
            evalStatus === TRACE_METRICS_STATUS.PASS
              ? 'success'
              : evalStatus === TRACE_METRICS_STATUS.FAIL
                ? 'error'
                : 'warning';

          const reviewConflicts =
            hasReview &&
            lastReview?.status?.name &&
            isPassedStatusName(lastReview.status.name) !==
              (evalStatus === TRACE_METRICS_STATUS.PASS);

          return (
            <Stack direction="row" spacing={0.5} alignItems="center">
              <Chip
                label={evalStatus}
                color={color}
                size="small"
                variant="outlined"
                sx={{ fontWeight: 500 }}
              />
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
        renderCell: params => {
          const env = params.value as string;
          if (!env) return null;

          const color =
            env === 'production'
              ? 'error'
              : env === 'staging'
                ? 'warning'
                : 'default';
          return (
            <Chip
              label={env}
              color={color}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 500 }}
            />
          );
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

  return (
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
      showToolbar={false}
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
  );
}
