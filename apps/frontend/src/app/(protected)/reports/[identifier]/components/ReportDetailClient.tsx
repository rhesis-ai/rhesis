'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  GlobalStyles,
  Stack,
} from '@mui/material';
import PublishIcon from '@mui/icons-material/PublishOutlined';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdfOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopyOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import { Fab, FabGroup } from '@/components/common/Fab';
import { DeleteModal } from '@/components/common/DeleteModal';
import { SectionCard } from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { can, useCan, useCanWithStatus } from '@/components/common/Can';
import { useNotifications } from '@/components/common/NotificationContext';
import { Capability } from '@/constants/capabilities';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { ReportDetail } from '@/utils/api-client/interfaces/report';
import ReportSummary from './ReportSummary';
import ReportRequirementsTable from './ReportRequirementsTable';
import ReportRunsTable from './ReportRunsTable';
import ReportSlot from './ReportSlot';
import ReportTitle from './ReportTitle';
import { EditRequirementsDrawer, EditRunsDrawer } from './EditSelectionDrawers';

const PRINT_ROOT = 'report-print-root';

// Print only the report: hide the app around it.
const printStyles = (
  <GlobalStyles
    styles={{
      '@media print': {
        'body *': { visibility: 'hidden' },
        [`#${PRINT_ROOT}, #${PRINT_ROOT} *`]: { visibility: 'visible' },
        [`#${PRINT_ROOT}`]: {
          position: 'absolute',
          left: 0,
          top: 0,
          width: '100%',
        },
      },
    }}
  />
);

function day(value?: string | null): string {
  return value ? format(new Date(value), 'dd/MM/yyyy') : '—';
}

export default function ReportDetailClient({
  initialReport,
}: {
  initialReport: ReportDetail;
}) {
  const router = useRouter();
  const notifications = useNotifications();
  const { allowed: canRead, loading } = useCanWithStatus(
    Capability.Report.READ
  );
  const canCreate = useCan(Capability.Report.CREATE);
  const [report, setReport] = React.useState(initialReport);
  const [confirmPublish, setConfirmPublish] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [editing, setEditing] = React.useState<'runs' | 'requirements' | null>(
    null
  );
  useDocumentTitle(report.title);

  const client = React.useMemo(
    () => new ApiClientFactory().getReportsClient(),
    []
  );
  const fail = React.useCallback(
    (message: string) =>
      notifications.show(message, {
        severity: 'error',
        autoHideDuration: 5000,
      }),
    [notifications]
  );
  const refresh = React.useCallback(async () => {
    setReport(await client.getReport(report.id));
  }, [client, report.id]);

  const isDraft = report.status === 'draft';
  const canEdit = isDraft && can(report, Capability.Report.UPDATE);

  const run = async (action: () => Promise<void>, error: string) => {
    setBusy(true);
    try {
      await action();
    } catch {
      fail(error);
    } finally {
      setBusy(false);
      setConfirmPublish(false);
      setConfirmDelete(false);
    }
  };

  const exportPdf = async () => {
    let recorded = false;
    await run(async () => {
      await client.recordExport(report.id);
      recorded = true;
    }, 'Failed to export the report');
    if (!recorded) return;
    // Print once the button is enabled again and its tooltip has closed, so the
    // print layout doesn't freeze an open tooltip in a stale position.
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    requestAnimationFrame(() => requestAnimationFrame(() => window.print()));
  };

  if (loading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="reports" />;

  const metadata = (
    <DetailMetadataStrip
      items={[
        {
          label: 'status:',
          value: isDraft ? 'Draft · live data' : 'Published · frozen',
        },
        { label: 'endpoint:', value: report.endpoint?.name ?? '—' },
        { label: 'created by:', value: report.user?.name || '—' },
        isDraft
          ? { label: 'created on:', value: day(report.created_at) }
          : { label: 'published on:', value: day(report.published_at) },
      ]}
    />
  );

  const actions = (
    <FabGroup sx={{ displayPrint: 'none' }}>
      {isDraft && can(report, Capability.Report.DELETE) && (
        <Fab
          icon={<DeleteOutlineIcon />}
          tooltip="Delete draft"
          aria-label="Delete draft"
          onClick={() => setConfirmDelete(true)}
          disabled={busy}
          sx={{ bgcolor: 'error.main', '&:hover': { bgcolor: 'error.dark' } }}
        />
      )}
      {can(report, Capability.Report.EXPORT) && (
        <Fab
          icon={<PictureAsPdfIcon />}
          tooltip="Export PDF"
          aria-label="Export PDF"
          disabled={busy}
          onClick={exportPdf}
        />
      )}
      {!isDraft && canCreate && (
        <Fab
          icon={<ContentCopyIcon />}
          tooltip="Copy as new draft"
          aria-label="Copy as new draft"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const draft = await client.copyReport(report.id);
              router.push(`/reports/${draft.id}`);
            }, 'Failed to copy the report')
          }
        />
      )}
      {isDraft && can(report, Capability.Report.PUBLISH) && (
        <Fab
          icon={<PublishIcon />}
          tooltip="Publish"
          aria-label="Publish"
          disabled={busy}
          onClick={() => setConfirmPublish(true)}
        />
      )}
    </FabGroup>
  );

  return (
    <PageLayout
      title={
        <ReportTitle
          title={report.title}
          canRename={canEdit}
          onRename={async title => {
            try {
              await client.updateReport(report.id, { title });
              await refresh();
            } catch {
              fail('Failed to rename the report');
            }
          }}
        />
      }
      breadcrumbs={[
        { label: 'Reports', href: '/reports' },
        { label: report.title, href: `/reports/${report.id}` },
      ]}
      metadata={metadata}
      actions={actions}
    >
      {printStyles}
      <Box id={PRINT_ROOT} sx={{ flexGrow: 1 }}>
        {isDraft && (
          <Alert severity="info" sx={{ mb: 3 }}>
            Draft: the numbers update as results change. Publishing freezes
            them.
          </Alert>
        )}
        {report.metrics?.versions_differ && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            The runs in this report tested different endpoint versions.
          </Alert>
        )}

        <ReportSummary report={report} editable={canEdit} onSaved={refresh} />
        <ReportSlot slot="after-summary" report={report} />
        <ReportRequirementsTable
          report={report}
          onEdit={canEdit ? () => setEditing('requirements') : undefined}
        />
        <ReportRunsTable
          report={report}
          onEdit={canEdit ? () => setEditing('runs') : undefined}
        />
        <ReportSlot slot="details" report={report} />

        {!isDraft && (
          <SectionCard
            title="Snapshot"
            subtitle="Hash over everything this report shows. A PDF can be checked against it."
          >
            <Stack spacing={3}>
              <ViewField
                label="Snapshot hash"
                value={report.snapshot_hash ?? undefined}
              />
              <ReportSlot slot="footer" report={report} />
            </Stack>
          </SectionCard>
        )}
      </Box>

      <Dialog open={confirmPublish} onClose={() => setConfirmPublish(false)}>
        <DialogTitle>Publish this report?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Publishing freezes the numbers, the counted results and the endpoint
            config. A published report can no longer be edited or deleted; you
            can copy it as a new draft.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmPublish(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await client.publishReport(report.id);
                await refresh();
              }, 'Failed to publish the report')
            }
          >
            Publish
          </Button>
        </DialogActions>
      </Dialog>

      {editing === 'runs' && (
        <EditRunsDrawer
          report={report}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}
      {editing === 'requirements' && (
        <EditRequirementsDrawer
          report={report}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}

      <DeleteModal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() =>
          run(async () => {
            await client.deleteReport(report.id);
            router.push('/reports');
          }, 'Failed to delete the report')
        }
        isLoading={busy}
        itemName={report.title}
        itemType="report"
      />
    </PageLayout>
  );
}
