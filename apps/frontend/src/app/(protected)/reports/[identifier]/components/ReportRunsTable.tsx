'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import { LinkOffIcon } from '@/components/icons';
import { gridEdgeInsetSx, withEdgeInset } from '@/components/reports/gridInset';
import { RESULT_RULES } from '@/components/reports/resultRules';
import { formatPassRate } from '@/components/reports/ReportSection';
import RunStatusChip from '@/components/reports/RunStatusChip';
import type {
  ReportDetail,
  ReportRunRow,
} from '@/utils/api-client/interfaces/report';

type Params = GridRenderCellParams<ReportRunRow>;

const COLUMNS: GridColDef[] = [
  {
    field: 'name',
    headerName: 'Run',
    flex: 1.5,
    renderCell: (params: Params) => params.row.name ?? params.row.id,
  },
  {
    field: 'test_set',
    headerName: 'Test set',
    flex: 2,
    renderCell: (params: Params) => params.row.test_set ?? '—',
  },
  {
    field: 'status',
    headerName: 'Status',
    flex: 1,
    renderCell: (params: Params) => (
      <RunStatusChip status={params.row.status} />
    ),
  },
  {
    field: 'created_at',
    headerName: 'Started',
    flex: 1,
    renderCell: (params: Params) =>
      params.row.created_at
        ? format(new Date(params.row.created_at), 'dd/MM/yyyy HH:mm')
        : '—',
  },
  {
    field: 'pass_rate',
    headerName: 'Pass rate',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    description: "The run's own pass rate over all its results",
    renderCell: (params: Params) => formatPassRate(params.row.pass_rate),
  },
  {
    field: 'results',
    headerName: 'Counted',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    description: 'Results from this run that the report counts',
  },
];

/** '60.0% to 92.6%' over runs that judged something; null with fewer than two. */
function rateSpread(runs: ReportRunRow[]): string | null {
  const rates = runs
    .map(run => run.pass_rate)
    .filter((rate): rate is number => typeof rate === 'number');
  if (rates.length < 2) return null;
  return `${formatPassRate(Math.min(...rates))} to ${formatPassRate(Math.max(...rates))}`;
}

function removeColumn(onRemove?: (id: string) => void): GridColDef[] {
  return onRemove
    ? [
        createRowActionsColumn({
          canDelete: () => true,
          onDelete: id => onRemove(id),
          deleteTooltip: 'Remove from report',
          deleteIcon: LinkOffIcon,
        }),
      ]
    : [];
}

export default function ReportRunsTable({
  report,
  onEdit,
  onRemove,
}: {
  report: ReportDetail;
  /** Set on an editable draft: shows the card's Assign button. */
  onEdit?: () => void;
  /** Set on an editable draft: a row action that takes the item out of the report. */
  onRemove?: (id: string) => void;
}) {
  const router = useRouter();
  const spread =
    report.result_rule === 'all'
      ? rateSpread(report.metrics?.runs ?? [])
      : null;
  const columns = React.useMemo(
    () => withEdgeInset([...COLUMNS, ...removeColumn(onRemove)]),
    [onRemove]
  );
  return (
    <Box sx={[{ mb: 3 }, gridEdgeInsetSx] as SxProps<Theme>}>
      <LinkedEntitiesGrid
        title="Test Runs"
        rows={report.metrics?.runs ?? []}
        columns={columns}
        getRowId={row => String(row.id)}
        onAssignClick={onEdit}
        onRowClick={params => router.push(`/test-runs/${String(params.id)}`)}
        searchPlaceholder="Search test runs…"
        emptyState={
          <Typography variant="body2" color="text.secondary">
            No test runs picked.
          </Typography>
        }
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mt: 1, px: 1 }}
      >
        {report.status === 'draft' && report.run_tag
          ? `Runs tagged “${report.run_tag}” join automatically until you publish. `
          : ''}
        {`Counting: ${RESULT_RULES[report.result_rule].label}. ${RESULT_RULES[report.result_rule].description}${spread ? ` Run pass rates range from ${spread}.` : ''}`}
      </Typography>
    </Box>
  );
}
