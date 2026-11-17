'use client';

import Link from 'next/link';
import { Typography } from '@mui/material';
import { FeatureName } from '@/constants/features';
import { Capability } from '@/constants/capabilities';
import { FeatureGate } from '@/contexts/FeaturesContext';
import { useCan } from '@/components/common/Can';
import ViewField from '@/components/common/ViewField';
import ReportFold, { ReportFoldRow } from '@/components/reports/ReportFold';
import type { ReportSectionProps } from '@/lib/extension-registries';
import { useReportAuditTrail } from '../useReportAuditTrail';
import type { ReportAuditEntry } from '../types';

const VERBS: Record<string, string> = {
  'report.published': 'Published',
  'report.exported': 'PDF exported',
};

/** The audit log, opened on this report's entries. */
export function auditLogUrl(reportId: string): string {
  return `/organizations/settings?tab=audit-log&resource_id=${reportId}`;
}

function when(entry: ReportAuditEntry): string {
  return new Date(entry.occurred_at).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function Trail({ report }: ReportSectionProps) {
  const { entries, loading, failed } = useReportAuditTrail(report.id, true);
  const canOpenLog = useCan(Capability.AuditLog.READ);
  const shown = entries.filter(e => e.action in VERBS);
  return (
    <ReportFold title="Audit trail">
      {loading && (
        <Typography variant="body2" color="text.secondary">
          Loading…
        </Typography>
      )}
      {failed && (
        <Typography variant="body2" color="text.secondary">
          The audit trail couldn&apos;t be loaded.
        </Typography>
      )}
      {!loading && !failed && shown.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No audit entries: published before the audit log was enabled, or
          removed after the retention period. The snapshot hash still checks the
          report.
        </Typography>
      )}
      {shown.map(entry => (
        <ReportFoldRow
          key={entry.id}
          label={`${VERBS[entry.action]}${entry.actor_label ? ` by ${entry.actor_label}` : ''}`}
        >
          {when(entry)}
        </ReportFoldRow>
      ))}
      {canOpenLog && (
        <Typography variant="body2" sx={{ mt: 1, displayPrint: 'none' }}>
          <Link href={auditLogUrl(report.id)}>
            Open in audit log, filtered to this report
          </Link>
        </Typography>
      )}
    </ReportFold>
  );
}

export function AuditTrailFold(props: ReportSectionProps) {
  if (props.report.status !== 'published') return null;
  return (
    <FeatureGate feature={FeatureName.AUDIT_LOG} fallback={null}>
      <Trail {...props} />
    </FeatureGate>
  );
}

function Recorded({ report }: ReportSectionProps) {
  const { entries } = useReportAuditTrail(report.id, true);
  const published = entries.find(e => e.action === 'report.published');
  if (!published) return null;
  return <ViewField label="Recorded in audit log" value={when(published)} />;
}

export function AuditFooterLine(props: ReportSectionProps) {
  if (props.report.status !== 'published') return null;
  return (
    <FeatureGate feature={FeatureName.AUDIT_LOG} fallback={null}>
      <Recorded {...props} />
    </FeatureGate>
  );
}
