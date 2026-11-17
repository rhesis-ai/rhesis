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
import { versionLabel } from '@/components/reports/version';
import { RESULT_RULES } from '@/components/reports/resultRules';
import type {
  ReportDetail,
  ReportRunRow,
} from '@/utils/api-client/interfaces/report';

type Params = GridRenderCellParams<ReportRunRow>;

const COLUMNS: GridColDef[] = [
  {
    field: 'name',
    headerName: 'Run',
    flex: 2,
    renderCell: (params: Params) => params.row.name ?? params.row.id,
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
    field: 'version',
    headerName: 'Version',
    flex: 1,
    sortable: false,
    renderCell: (params: Params) =>
      versionLabel(params.row.version_info) ?? '—',
  },
  {
    field: 'results',
    headerName: 'Results counted',
    width: 160,
    align: 'right',
    headerAlign: 'right',
  },
];

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
        {`Counting: ${RESULT_RULES[report.result_rule].label}. ${RESULT_RULES[report.result_rule].description}`}
      </Typography>
    </Box>
  );
}
