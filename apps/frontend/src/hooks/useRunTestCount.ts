'use client';

import { useEffect, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { anyTagFilter } from '@/utils/odata-filter';

/**
 * How many tests a Run click will execute: the tests in each test set (only
 * those carrying any of `testsTagged`, when given), times the runs started
 * per test set (one per experiment version). The backend checks this total
 * against the quota, so the drawer can too.
 *
 * `null` while loading, when disabled, or if a count fails -- the caller
 * treats that as unknown and lets the backend's 402 decide.
 */
export function useRunTestCount(
  testSetIds: string[],
  runsPerTestSet: number,
  enabled: boolean,
  testsTagged: string[] = []
): number | null {
  const key = JSON.stringify([testSetIds, testsTagged]);
  const [counted, setCounted] = useState<{
    key: string;
    tests: number;
  } | null>(null);

  useEffect(() => {
    const [ids, tagged] = JSON.parse(key) as [string[], string[]];
    if (!enabled || ids.length === 0) return;
    let cancelled = false;
    const client = new ApiClientFactory().getTestSetsClient();
    const filter = tagged.length > 0 ? anyTagFilter(tagged) : undefined;
    Promise.all(
      ids.map(id =>
        client.getTestSetTests(id, {
          limit: 1,
          ...(filter ? { $filter: filter } : {}),
        })
      )
    )
      .then(pages => {
        if (cancelled) return;
        const tests = pages.reduce(
          (sum, page) => sum + page.pagination.totalCount,
          0
        );
        setCounted({ key, tests });
      })
      .catch(() => {
        if (!cancelled) setCounted(null);
      });
    return () => {
      cancelled = true;
    };
  }, [key, enabled]);

  if (!enabled || !counted || counted.key !== key) return null;
  return counted.tests * runsPerTestSet;
}
