'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import { type GridColDef, type GridRenderCellParams } from '@mui/x-data-grid';
import { formatDistanceToNow } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, can, useCan } from '@/components/common/Can';
import EntityGrid, {
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { ReportsIcon } from '@/components/icons';
import { Capability } from '@/constants/capabilities';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { Report } from '@/utils/api-client/interfaces/report';
import ReportStatusChip from './ReportStatusChip';
import ReportCreateDrawer from './create/ReportCreateDrawer';
import { reportsList } from './list';

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Draft', value: 'draft' },
  { label: 'Published', value: 'published' },
];

function toFilters(state: EntityGridFilterState<Record<string, never>>) {
  return { search: state.search, status: state.pill };
}

function relative(value?: string | null): string {
  return value
    ? formatDistanceToNow(new Date(value), { addSuffix: true })
    : '—';
}

const COLUMNS: GridColDef[] = [
  {
    field: 'title',
    headerName: 'Title',
    flex: 1.5,
    renderCell: (params: GridRenderCellParams<Report>) => (
      <Box component="span" sx={{ fontWeight: 500 }}>
        {params.row.title}
      </Box>
    ),
  },
  {
    field: 'endpoint',
    headerName: 'Endpoint',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<Report>) =>
      params.row.endpoint?.name ?? '—',
  },
  {
    field: 'is_release',
    headerName: 'Type',
    width: 130,
    description: 'Release reports end with a ship recommendation',
    renderCell: (params: GridRenderCellParams<Report>) =>
      params.row.is_release ? 'Release' : 'General',
  },
  {
    field: 'status',
    headerName: 'Status',
    width: 130,
    renderCell: (params: GridRenderCellParams<Report>) => (
      <ReportStatusChip status={params.row.status} />
    ),
  },
  {
    field: 'user',
    headerName: 'Author',
    flex: 1,
    sortable: false,
    renderCell: (params: GridRenderCellParams<Report>) =>
      params.row.user?.name || params.row.user?.email || '—',
  },
  {
    field: 'published_at',
    headerName: 'Published',
    flex: 1,
    renderCell: (params: GridRenderCellParams<Report>) =>
      relative(params.row.published_at),
  },
];

interface ReportsPageClientProps {
  initialData?: Report[];
  initialTotalCount?: number;
}

export default function ReportsPageClient({
  initialData,
  initialTotalCount = 0,
}: ReportsPageClientProps) {
  const gate = useListAuthGate(reportsList);
  const canCreate = useCan(Capability.Report.CREATE);
  const [createOpen, setCreateOpen] = React.useState(false);
  const goToCreate = React.useCallback(() => setCreateOpen(true), []);

  useDocumentTitle('Reports');

  if (!gate.ready) return gate.node;

  return (
    <PageLayout
      title="Reports"
      description="Summaries of an endpoint's test runs, for a release or a review. Drafts stay live; published reports are frozen."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Report.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="New Report"
              aria-label="New Report"
              onClick={goToCreate}
            />
          </Can>
        </FabGroup>
      }
    >
      <Box sx={{ mt: 2, mb: 2 }}>
        <EntityGrid<Report, typeof reportsList.filters>
          descriptor={reportsList}
          columns={COLUMNS}
          toFilters={toFilters}
          emptyState={
            <EntityEmptyState
              card
              icon={ReportsIcon}
              title="No reports yet"
              description="Pick an endpoint, the test runs that count and the requirements they cover. You get a report you can publish and export as PDF."
              actionLabel={canCreate ? 'Create report' : undefined}
              onAction={canCreate ? goToCreate : undefined}
            />
          }
          initialData={initialData}
          initialTotalCount={initialTotalCount}
          searchPlaceholder="Search reports…"
          pills={{ tabs: STATUS_TABS }}
          getRowUrl={row => `/reports/${row.id}`}
          editAction={{
            // Published reports are frozen: no edit icon for them.
            can: row => can(row, Capability.Report.UPDATE),
          }}
          storageKey="reports-grid"
          pageSizeOptions={[10, 25, 50]}
        />
      </Box>
      <ReportCreateDrawer
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </PageLayout>
  );
}
