'use client';

import { useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import { Chip, Box, Typography, Tooltip } from '@mui/material';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
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
  filters: { project_id?: string };
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
  filters,
}: TracesTableProps) {
  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'trace_id',
        headerName: 'Trace ID',
        width: 150,
        renderCell: params => {
          const traceId = params.value as string;
          const truncated = `${traceId.slice(0, 8)}...${traceId.slice(-8)}`;
          return (
            <Tooltip title={traceId}>
              <Typography
                variant="body2"
                sx={{ fontFamily: 'monospace', cursor: 'pointer' }}
              >
                {truncated}
              </Typography>
            </Tooltip>
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
          const timeAgo = formatDistanceToNow(new Date(params.value), {
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
        field: 'status_code',
        headerName: 'Status',
        width: 100,
        renderCell: params => {
          const status = params.value as string;
          return (
            <Chip
              label={status}
              color={status === 'OK' ? 'success' : 'error'}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 500 }}
            />
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

  const handleRowClick = (params: any) => {
    onRowClick(params.row.trace_id, params.row.project_id);
  };

  if (!traces || traces.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          py: 8,
          textAlign: 'center',
        }}
      >
        <Typography variant="h6" color="text.secondary" gutterBottom>
          No traces found
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {!filters.project_id
            ? 'No traces available across all projects. Try adjusting your filters or check back later.'
            : 'No traces found for the selected project. Try adjusting your filters or check back later.'}
        </Typography>
      </Box>
    );
  }

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
