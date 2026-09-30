'use client';

import React, { useMemo } from 'react';
import type {
  GridColDef,
  GridRowParams,
  GridSortModel,
} from '@mui/x-data-grid';
import { Box, Tooltip, Typography } from '@mui/material';
import { formatDistanceToNowStrict } from 'date-fns';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridBadge from '@/components/common/GridBadge';
import ModelLabel from '@/components/common/ModelLabel';
import UsageCell from '@/components/common/UsageCell';
import { getSpanTypeInfo } from '@/constants/span-types';
import { useCurrency } from '@/contexts/CurrencyContext';
import type { SpanSummary } from '@/utils/api-client/interfaces/telemetry';
import { formatDate } from '@/utils/date';
import { formatDuration } from '@/utils/format-duration';
import { formatTokenCount, tokenSplitLabel } from '@/utils/trace-utils';
import TracesToolbar from './TracesToolbar';

/** For looking a span up, not for scanning the list. */
const COLUMNS_HIDDEN_BY_DEFAULT = {
  span_id: false,
  trace_id: false,
  is_root: false,
  input_tokens: false,
  output_tokens: false,
} as const;

function Dash() {
  return (
    <Typography variant="body2" sx={{ color: 'text.disabled' }}>
      —
    </Typography>
  );
}

function MonoText({ value }: { value: string | null | undefined }) {
  if (!value) return <Dash />;
  return (
    <Tooltip title={value}>
      <Typography
        variant="body2"
        sx={{
          fontFamily: 'monospace',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {value}
      </Typography>
    </Tooltip>
  );
}

function SpanTypeCell({ type }: { type: string }) {
  const info = getSpanTypeInfo(type);
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
      <Box
        component={info.icon}
        sx={{
          fontSize: theme => theme.spacing(2.25),
          color: info.color,
          flexShrink: 0,
        }}
      />
      <Typography variant="body2" noWrap>
        {info.label}
      </Typography>
    </Box>
  );
}

interface SpansTableProps {
  spans: SpanSummary[];
  loading: boolean;
  onRowClick: (span: SpanSummary) => void;
  totalCount: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  sortModel?: GridSortModel;
  onSortModelChange?: (model: GridSortModel) => void;
}

/**
 * One row per span. Toolbar state comes from `TracesToolbarContext`, provided by
 * `TracesClient`. Sortable columns are the ones `GET /telemetry/spans` sorts by.
 */
export default function SpansTable({
  spans,
  loading,
  onRowClick,
  totalCount,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  sortModel,
  onSortModelChange,
}: SpansTableProps) {
  const { format: money, alternativesTitle } = useCurrency();

  const columns: GridColDef<SpanSummary>[] = useMemo(
    () => [
      {
        field: 'span_type',
        headerName: 'Type',
        sortable: false,
        flex: 1.2,
        minWidth: 110,
        renderCell: params => <SpanTypeCell type={params.row.span_type} />,
      },
      {
        field: 'span_name',
        headerName: 'Name',
        flex: 2.4,
        minWidth: 140,
        renderCell: params => <MonoText value={params.row.span_name} />,
      },
      {
        field: 'trace_name',
        headerName: 'Trace',
        sortable: false,
        flex: 2,
        minWidth: 120,
        renderCell: params => <MonoText value={params.row.trace_name} />,
      },
      {
        field: 'start_time',
        headerName: 'Started',
        flex: 1.3,
        minWidth: 100,
        renderCell: params => (
          <Tooltip title={formatDate(params.row.start_time)}>
            <Typography variant="body2">
              {formatDistanceToNowStrict(new Date(params.row.start_time), {
                addSuffix: true,
              })}
            </Typography>
          </Tooltip>
        ),
      },
      {
        field: 'duration_ms',
        headerName: 'Duration',
        flex: 1,
        minWidth: 80,
        align: 'right',
        renderCell: params => (
          <Typography variant="body2">
            {formatDuration(params.row.duration_ms)}
          </Typography>
        ),
      },
      {
        field: 'model',
        headerName: 'Model',
        sortable: false,
        flex: 1.6,
        minWidth: 120,
        renderCell: params => (
          <ModelLabel
            models={params.row.model ? [params.row.model] : []}
            providers={params.row.provider ? [params.row.provider] : []}
          />
        ),
      },
      {
        field: 'total_tokens',
        headerName: 'Tokens',
        flex: 0.9,
        minWidth: 70,
        align: 'right',
        renderCell: params => (
          <UsageCell
            value={params.row.total_tokens}
            format={formatTokenCount}
            title={tokenSplitLabel(
              params.row.input_tokens,
              params.row.output_tokens
            )}
          />
        ),
      },
      {
        field: 'cost_usd',
        headerName: 'Cost',
        flex: 0.9,
        minWidth: 70,
        align: 'right',
        renderCell: params => {
          const cost = params.row.cost_usd;
          return (
            <UsageCell
              value={cost}
              format={money}
              title={
                typeof cost === 'number' ? alternativesTitle(cost) : undefined
              }
            />
          );
        },
      },
      {
        field: 'status_code',
        headerName: 'Status',
        sortable: false,
        flex: 0.8,
        minWidth: 70,
        renderCell: params =>
          params.row.status_code === 'ERROR' ? (
            <GridBadge label="Error" />
          ) : (
            <Typography variant="body2" color="text.secondary">
              OK
            </Typography>
          ),
      },
      {
        field: 'environment',
        headerName: 'Environment',
        sortable: false,
        flex: 1,
        minWidth: 90,
        renderCell: params => {
          const env = params.row.environment;
          if (!env) return null;
          return (
            <GridBadge label={env.charAt(0).toUpperCase() + env.slice(1)} />
          );
        },
      },
      {
        field: 'span_id',
        headerName: 'Span ID',
        sortable: false,
        flex: 1.2,
        minWidth: 100,
        renderCell: params => <MonoText value={params.row.span_id} />,
      },
      {
        field: 'trace_id',
        headerName: 'Trace ID',
        sortable: false,
        flex: 1.2,
        minWidth: 100,
        renderCell: params => <MonoText value={params.row.trace_id} />,
      },
      {
        field: 'is_root',
        headerName: 'Root',
        sortable: false,
        flex: 0.6,
        minWidth: 60,
        renderCell: params => (
          <Typography variant="body2">
            {params.row.is_root ? 'Yes' : 'No'}
          </Typography>
        ),
      },
      {
        field: 'input_tokens',
        headerName: 'Input tokens',
        sortable: false,
        flex: 1,
        minWidth: 90,
        align: 'right',
        renderCell: params => (
          <UsageCell
            value={params.row.input_tokens}
            format={formatTokenCount}
          />
        ),
      },
      {
        field: 'output_tokens',
        headerName: 'Output tokens',
        sortable: false,
        flex: 1,
        minWidth: 90,
        align: 'right',
        renderCell: params => (
          <UsageCell
            value={params.row.output_tokens}
            format={formatTokenCount}
          />
        ),
      },
    ],
    // Rebuilt when the currency changes, so the cost column reformats.
    [money, alternativesTitle]
  );

  return (
    <BaseDataGrid
      rows={spans}
      columns={columns}
      loading={loading}
      getRowId={row => row.id}
      onRowClick={(params: GridRowParams<SpanSummary>) =>
        onRowClick(params.row)
      }
      serverSidePagination
      totalRows={totalCount}
      paginationModel={{ page, pageSize }}
      onPaginationModelChange={model => {
        if (model.page !== page) onPageChange(model.page);
        if (model.pageSize !== pageSize) onPageSizeChange(model.pageSize);
      }}
      pageSizeOptions={[25, 50, 100]}
      disablePaperWrapper
      sortingMode="server"
      sortModel={sortModel}
      onSortModelChange={onSortModelChange}
      toolbarSlot={TracesToolbar}
      persistState
      storageKey="spans-grid-v1"
      initialState={{
        columns: { columnVisibilityModel: { ...COLUMNS_HIDDEN_BY_DEFAULT } },
      }}
      sx={{
        '& .MuiDataGrid-row': { cursor: 'pointer' },
        '& .MuiDataGrid-cell': { borderBottom: 1, borderColor: 'divider' },
      }}
    />
  );
}
