'use client';

import * as React from 'react';
import { Box, Chip, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import { formatPassRate } from '@/components/reports/ReportSection';
import { gridEdgeInsetSx, withEdgeInset } from '@/components/reports/gridInset';
import type {
  ReportDetail,
  ReportMetricKind,
  ReportMetricResult,
} from '@/utils/api-client/interfaces/report';

const KIND_LABELS: Record<ReportMetricKind, { label: string; hint: string }> = {
  llm: { label: 'LLM', hint: 'An LLM judge' },
  jev: { label: 'JEV', hint: 'A classifier with a Jev decision model' },
  code: { label: 'Code', hint: 'A code check' },
};

interface Row extends Partial<ReportMetricResult> {
  id: string;
  name: string;
  group: boolean;
}

type Params = GridRenderCellParams<Row>;

const COLUMNS: GridColDef[] = withEdgeInset([
  {
    field: 'name',
    headerName: 'Requirement / metric',
    flex: 2,
    sortable: false,
    renderCell: (params: Params) => (
      <Box
        component="span"
        sx={{
          pl: params.row.group ? 0 : 3,
          fontWeight: params.row.group ? 600 : undefined,
        }}
      >
        {params.row.name}
      </Box>
    ),
  },
  {
    field: 'kind',
    headerName: 'Kind',
    width: 110,
    sortable: false,
    renderCell: (params: Params) =>
      params.row.kind ? (
        <Chip
          size="small"
          variant="outlined"
          label={KIND_LABELS[params.row.kind].label}
          title={KIND_LABELS[params.row.kind].hint}
        />
      ) : (
        ''
      ),
  },
  {
    field: 'passed',
    headerName: 'Passed',
    width: 100,
    align: 'right',
    headerAlign: 'right',
    sortable: false,
  },
  {
    field: 'failed',
    headerName: 'Failed',
    width: 100,
    align: 'right',
    headerAlign: 'right',
    sortable: false,
    renderCell: (params: Params) =>
      params.row.group ? (
        ''
      ) : (
        <Typography
          variant="body2"
          color={(params.row.failed ?? 0) > 0 ? 'error.main' : undefined}
        >
          {params.row.failed}
        </Typography>
      ),
  },
  {
    field: 'pass_rate',
    headerName: 'Pass rate',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    sortable: false,
    renderCell: (params: Params) =>
      params.row.group ? '' : formatPassRate(params.row.pass_rate),
  },
]);

/** Each requirement with the metrics that judged it: their kind and how they scored. */
export default function ReportMetricsTable({
  report,
}: {
  report: ReportDetail;
}) {
  const results = report.metrics?.metric_results;
  const rows = React.useMemo<Row[]>(
    () =>
      (results ?? []).flatMap(group => [
        { id: `req-${group.requirement_id}`, name: group.name, group: true },
        ...group.metrics.map(metric => ({
          ...metric,
          id: `${group.requirement_id}-${metric.name}`,
          group: false,
        })),
      ]),
    [results]
  );
  if (rows.length === 0) return null;
  return (
    <Box sx={[{ mb: 3 }, gridEdgeInsetSx] as SxProps<Theme>}>
      <LinkedEntitiesGrid
        title="Metrics"
        rows={rows}
        columns={COLUMNS}
        getRowId={row => String(row.id)}
        searchPlaceholder="Search metrics…"
        pageSizeOptions={[10, 25, 50]}
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mt: 1, px: 1 }}
      >
        How each metric judged the requirement&apos;s counted results. LLM: an
        LLM judge. JEV: a classifier with a Jev model. Code: a code check.
      </Typography>
    </Box>
  );
}
