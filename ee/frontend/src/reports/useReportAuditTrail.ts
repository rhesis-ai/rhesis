'use client';

import * as React from 'react';
import type { ReportAuditEntry } from './types';
import { ReportAuditClient } from './api';

// The trail and the footer line both read it; one request per report and page view.
const inFlight = new Map<string, Promise<ReportAuditEntry[]>>();

export function useReportAuditTrail(
  reportId: string,
  enabled: boolean
): { entries: ReportAuditEntry[]; loading: boolean; failed: boolean } {
  const [entries, setEntries] = React.useState<ReportAuditEntry[]>([]);
  const [loading, setLoading] = React.useState(enabled);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let request = inFlight.get(reportId);
    if (!request) {
      request = new ReportAuditClient().getAuditTrail(reportId);
      inFlight.set(reportId, request);
      request.finally(() => inFlight.delete(reportId)).catch(() => undefined);
    }
    request
      .then(result => {
        if (!cancelled) setEntries(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportId, enabled]);

  return { entries, loading, failed };
}
