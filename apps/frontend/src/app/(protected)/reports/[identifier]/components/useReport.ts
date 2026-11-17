'use client';

import * as React from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ReportDetail,
  ReportUpdate,
} from '@/utils/api-client/interfaces/report';

/** Thrown when a save went through but the page couldn't reload the report. */
export class ReportReloadError extends Error {}

/**
 * The report on the detail page and the one way to change it.
 *
 * Saves run one after another, and a body given as a function is built from the
 * report as the previous save left it, so two quick removals both stick.
 */
export function useReport(initialReport: ReportDetail) {
  const client = React.useMemo(
    () => new ApiClientFactory().getReportsClient(),
    []
  );
  const [report, setReport] = React.useState(initialReport);
  const latest = React.useRef(initialReport);
  const queue = React.useRef<Promise<unknown>>(Promise.resolve());
  const id = initialReport.id;

  const refresh = React.useCallback(async () => {
    let fresh: ReportDetail;
    try {
      fresh = await client.getReport(id);
    } catch (error) {
      throw new ReportReloadError(String(error));
    }
    latest.current = fresh;
    setReport(fresh);
  }, [client, id]);

  const update = React.useCallback(
    (body: ReportUpdate | ((current: ReportDetail) => ReportUpdate)) => {
      const next = queue.current.then(async () => {
        const resolved =
          typeof body === 'function' ? body(latest.current) : body;
        await client.updateReport(id, resolved);
        await refresh();
      });
      // A failed save mustn't block the ones queued after it.
      queue.current = next.catch(() => undefined);
      return next;
    },
    [client, id, refresh]
  );

  return { report, client, refresh, update };
}
