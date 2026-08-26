'use client';

import { useEffect, useState } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UUID } from 'crypto';

/**
 * Whether this metric is a custom one, and so can be tuned.
 *
 * Only custom metrics can be tuned — a framework-provided metric has an
 * evaluation prompt the organization does not own. The backend refuses the
 * tuning routes for anything else, so without this the Tuning tab would appear
 * on a `rhesis` metric (the detail page serves those too) and every call it
 * made would come back 400.
 *
 * Fails closed: false while loading and on error, so the tab never flashes in
 * for a metric that cannot use it.
 */
export function useIsCustomMetric(metricId: string): boolean {
  const [isCustom, setIsCustom] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const metric = await new ApiClientFactory()
          .getMetricsClient()
          .getMetric(metricId as UUID);
        if (cancelled) return;
        setIsCustom(
          metric.backend_type?.type_value?.toLowerCase() === 'custom'
        );
      } catch {
        if (!cancelled) setIsCustom(false);
      }
    };

    check();
    return () => {
      cancelled = true;
    };
  }, [metricId]);

  return isCustom;
}
