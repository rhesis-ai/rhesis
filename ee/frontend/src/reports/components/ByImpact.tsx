'use client';

import { Typography } from '@mui/material';
import type { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import ReportSectionBlock, {
  formatPassRate,
} from '@/components/reports/ReportSection';
import type {
  ReportColumnCellProps,
  ReportSectionProps,
} from '@/lib/extension-registries';
import { byImpactOf, type ImpactRow } from '../types';

type Params = GridRenderCellParams<ImpactRow>;

const columnsFor = (rule: string): GridColDef[] => [
  { field: 'name', headerName: 'Impact', flex: 2, sortable: false },
  {
    field: 'requirements_tested',
    headerName: 'Requirements tested',
    flex: 1,
    sortable: false,
    renderCell: (params: Params) =>
      `${params.row.requirements_tested} of ${params.row.requirements_total}`,
  },
  {
    field: 'tests',
    headerName: rule === 'all' ? 'Results' : 'Tests',
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
    renderCell: (params: Params) => (
      <Typography
        variant="body2"
        color={params.row.failed > 0 ? 'error.main' : undefined}
      >
        {params.row.failed}
      </Typography>
    ),
  },
  {
    field: 'pass_rate',
    headerName: 'Pass rate',
    width: 160,
    align: 'right',
    headerAlign: 'right',
    sortable: false,
    renderCell: (params: Params) => formatPassRate(params.row.pass_rate),
  },
];

function ByImpactTable({ report }: ReportSectionProps) {
  const section = byImpactOf(report);
  if (!section) return null;
  return (
    <ReportSectionBlock
      title="By impact"
      subtitle="Only impacts with a requirement tested in this report."
      aside={
        <Typography variant="body2" color="text.secondary">
          Pass rate overall:{' '}
          <Typography component="span" variant="subtitle2" color="text.primary">
            {formatPassRate(report.metrics?.totals.pass_rate)}
          </Typography>
        </Typography>
      }
    >
      {section.impacts.length > 0 && (
        <BaseDataGrid
          rows={section.impacts}
          columns={columnsFor(report.result_rule)}
          getRowId={row => String(row.name)}
          disablePaperWrapper
          hideFooter
        />
      )}
    </ReportSectionBlock>
  );
}

// No FeatureGate here or on the cell: the backend sends by_impact only when it built
// or froze it for an entitled org, so a published report keeps it after a licence change.
export function ByImpactSection(props: ReportSectionProps) {
  return <ByImpactTable {...props} />;
}

export function ImpactCell({ report, row }: ReportColumnCellProps) {
  const name = byImpactOf(report)?.requirements[row.id];
  return (
    <Typography variant="body2" color="text.secondary" noWrap>
      {row.level === 0 && !name ? '' : (name ?? '')}
    </Typography>
  );
}
