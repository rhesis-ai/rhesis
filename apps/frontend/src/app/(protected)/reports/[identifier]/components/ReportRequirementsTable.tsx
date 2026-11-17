'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import { getReportRequirementColumns } from '@/lib/extension-registries';
import { formatPassRate } from '@/components/reports/ReportSection';
import type {
  ReportDetail,
  ReportRequirementRow,
} from '@/utils/api-client/interfaces/report';

const UNTESTED: Record<string, string> = {
  no_tests: 'No tests yet',
  not_in_runs: 'Not in these runs',
  errored_only: 'Every test errored',
};

type Params = GridRenderCellParams<ReportRequirementRow>;

export default function ReportRequirementsTable({
  report,
  onEdit,
}: {
  report: ReportDetail;
  /** Set on an editable draft: shows the card's Assign button. */
  onEdit?: () => void;
}) {
  const router = useRouter();
  const rows = report.metrics?.requirements ?? [];

  const columns = React.useMemo<GridColDef[]>(() => {
    // Columns EE registered whose data the backend sent (e.g. Impact).
    const extra: GridColDef[] = getReportRequirementColumns()
      .filter(column => column.sectionKey in report.sections)
      .map(column => {
        const Cell = column.cell;
        return {
          field: `ext_${column.id}`,
          headerName: column.header,
          flex: 1,
          sortable: false,
          renderCell: (params: Params) => (
            <Cell report={report} row={params.row} />
          ),
        };
      });
    return [
      {
        field: 'name',
        headerName: 'Requirement',
        flex: 2,
        sortable: false,
        renderCell: (params: Params) => (
          <Box
            component="span"
            sx={{
              pl: params.row.level * 3,
              fontWeight: params.row.level === 0 ? 600 : undefined,
            }}
          >
            {params.row.name}
          </Box>
        ),
      },
      ...extra,
      {
        field: 'tests',
        headerName: 'Tests',
        width: 100,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params: Params) => params.row.tests || '',
      },
      {
        field: 'failed',
        headerName: 'Failed',
        width: 100,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params: Params) =>
          params.row.coverage === 'tested' ? (
            <Typography
              variant="body2"
              color={params.row.failed > 0 ? 'error.main' : undefined}
            >
              {params.row.failed}
            </Typography>
          ) : (
            ''
          ),
      },
      {
        field: 'pass_rate',
        headerName: 'Pass rate',
        width: 160,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params: Params) =>
          params.row.coverage === 'tested' ? (
            formatPassRate(params.row.pass_rate)
          ) : (
            <Typography variant="body2" color="text.secondary">
              {UNTESTED[params.row.coverage]}
            </Typography>
          ),
      },
    ];
  }, [report]);

  return (
    <Box sx={{ mb: 3 }}>
      <LinkedEntitiesGrid
        title="Requirements"
        rows={rows}
        columns={columns}
        getRowId={row => String(row.id)}
        onAssignClick={onEdit}
        onRowClick={params => router.push(`/requirements/${String(params.id)}`)}
        searchPlaceholder="Search requirements…"
        pageSizeOptions={[10, 25, 50]}
        emptyState={
          <Typography variant="body2" color="text.secondary">
            No requirements picked. The key numbers still count every result.
          </Typography>
        }
      />
    </Box>
  );
}
