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
import { detailPageTitle } from '@/utils/document-title';
import type {
  ReportDetail,
  ReportUpdate,
} from '@/utils/api-client/interfaces/report';
import ReportSetup from './ReportSetup';
import ReportSummary from './ReportSummary';
import ReportRequirementsTable from './ReportRequirementsTable';
import ReportRunsTable from './ReportRunsTable';
import ReportMetricsTable from './ReportMetricsTable';
import { RESULT_RULES } from '@/components/reports/resultRules';
import ReportSlot from './ReportSlot';
import ReportTitle from './ReportTitle';
import { EditRequirementsDrawer, EditRunsDrawer } from './EditSelectionDrawers';
import { ReportReloadError, useReport } from './useReport';

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
  const { report, client, refresh, update } = useReport(initialReport);
  // Cards with an open edit form; publishing waits until they're saved or cancelled.
  const [openEdits, setOpenEdits] = React.useState<Set<string>>(new Set());
  const trackEditing = React.useCallback(
    (card: string) => (isEditing: boolean) =>
      setOpenEdits(current => {
        if (current.has(card) === isEditing) return current;
        const next = new Set(current);
        if (isEditing) next.add(card);
        else next.delete(card);
        return next;
      }),
    []
  );
  const onSetupEditing = React.useMemo(
    () => trackEditing('Setup'),
    [trackEditing]
  );
  const onSummaryEditing = React.useMemo(
    () => trackEditing('Summary'),
    [trackEditing]
  );
  const [confirmPublish, setConfirmPublish] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [editing, setEditing] = React.useState<'runs' | 'requirements' | null>(
    null
  );
  useDocumentTitle(detailPageTitle(report.title, 'Reports'));

  const fail = React.useCallback(
    (message: string) =>
      notifications.show(message, {
        severity: 'error',
        autoHideDuration: 5000,
      }),
    [notifications]
  );
  const isDraft = report.status === 'draft';
  const canEdit = isDraft && can(report, Capability.Report.UPDATE);

  const run = async (action: () => Promise<void>, error: string) => {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      fail(
        e instanceof ReportReloadError
          ? 'Saved, but the page could not reload. Refresh the page.'
          : error
      );
    } finally {
      setBusy(false);
      setConfirmPublish(false);
      setConfirmDelete(false);
    }
  };

  // Built from the report as the previous queued save left it, so quick removals add up.
  const remove = (body: (current: ReportDetail) => ReportUpdate) =>
    update(body).catch(e =>
      fail(
        e instanceof ReportReloadError
          ? 'Saved, but the page could not reload. Refresh the page.'
          : 'Failed to update the report'
      )
    );

  const exportPdf = () =>
    run(async () => {
      const { blob, filename } = await client.downloadPdf(report.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    }, 'Failed to export the report');

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
        { label: 'counting:', value: RESULT_RULES[report.result_rule].label },
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
              await update({ title });
              return true;
            } catch (e) {
              return e instanceof ReportReloadError;
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
      <Box sx={{ flexGrow: 1 }}>
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

        <ReportSetup
          report={report}
          editable={canEdit}
          update={update}
          onEditingChange={onSetupEditing}
        />
        <ReportSummary
          report={report}
          editable={canEdit}
          update={update}
          onEditingChange={onSummaryEditing}
        />
        <ReportSlot slot="after-summary" report={report} />
        <ReportRequirementsTable
          report={report}
          onEdit={canEdit ? () => setEditing('requirements') : undefined}
          onRemove={
            canEdit
              ? id =>
                  remove(current => ({
                    requirement_ids: current.requirement_ids.filter(
                      r => String(r) !== id
                    ),
                  }))
              : undefined
          }
        />
        <ReportMetricsTable report={report} />
        <ReportRunsTable
          report={report}
          onEdit={canEdit ? () => setEditing('runs') : undefined}
          onRemove={
            // A tag decides the runs of a tag report; change the tag instead.
            canEdit && !report.run_tag
              ? id =>
                  remove(current => ({
                    test_run_ids: current.test_run_ids.filter(
                      r => String(r) !== id
                    ),
                  }))
              : undefined
          }
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
          {openEdits.size > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              {[...openEdits].join(' and ')} has unsaved changes. Save or cancel
              them first, or they won&apos;t be in the published report.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmPublish(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={busy || openEdits.size > 0}
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
          update={update}
        />
      )}
      {editing === 'requirements' && (
        <EditRequirementsDrawer
          report={report}
          onClose={() => setEditing(null)}
          update={update}
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
