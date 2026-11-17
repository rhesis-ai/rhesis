'use client';

import * as React from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import type { RequirementOptionRow } from './RequirementsStep';

const PAGE_LIMIT = 100;

/** The endpoint's test runs, for picking. */
export function useEndpointRuns(endpointId: string, enabled = true) {
  const [runs, setRuns] = React.useState<TestRunDetail[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!enabled || !endpointId) return;
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    new ApiClientFactory()
      .getTestRunsClient()
      .getTestRuns({
        skip: 0,
        limit: PAGE_LIMIT,
        filter: `test_configuration/endpoint_id eq '${endpointId}'`,
      })
      .then(page => !cancelled && setRuns(page.data))
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [endpointId, enabled]);

  return { runs, loading, failed };
}

/** Every requirement, and which of them the given runs tested. */
export function useRequirementOptions(runIds: string[], enabled = true) {
  const [requirements, setRequirements] = React.useState<
    RequirementOptionRow[]
  >([]);
  const [tested, setTested] = React.useState<Set<string>>(new Set());
  const [loading, setLoading] = React.useState(false);
  const [failed, setFailed] = React.useState(false);
  /** The runs `tested` was computed for; differs from the input while loading. */
  const [loadedFor, setLoadedFor] = React.useState<string | null>(null);
  const runKey = [...runIds].sort().join(',');

  React.useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const factory = new ApiClientFactory();
    const ids = runKey ? runKey.split(',') : [];
    setLoading(true);
    setFailed(false);
    Promise.all([
      factory.getRequirementClient().getRequirements({ limit: PAGE_LIMIT }),
      ...ids.map(id => factory.getTestRunsClient().getTestRunRequirements(id)),
    ])
      .then(([all, ...perRun]) => {
        if (cancelled) return;
        setRequirements(
          all.map(r => ({
            id: String(r.id),
            name: r.name,
            parent_id: r.parent_id ? String(r.parent_id) : null,
          }))
        );
        setTested(new Set(perRun.flatMap(list => list.map(r => String(r.id)))));
        setLoadedFor(runKey);
      })
      .catch(() => !cancelled && setFailed(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [runKey, enabled]);

  return {
    requirements,
    tested,
    loading,
    failed,
    ready: loadedFor === runKey,
  };
}
