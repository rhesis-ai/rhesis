import * as React from 'react';
import { redirect } from 'next/navigation';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import MetricDetailPageTabs from './MetricDetailPageTabs';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import {
  fetchMetricLinkedRequirements,
  fetchMetricTuning,
  isCustomMetric,
} from './metric-data';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function MetricDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const apiFactory = await createServerApiFactory();
  const client = apiFactory.getMetricsClient();

  let metric: MetricDetail;
  try {
    metric = await client.getMetric(identifier as UUID);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  // The detail page only knows how to render rhesis and custom metrics.
  const backendType = metric.backend_type?.type_value?.toLowerCase();
  if (backendType !== 'rhesis' && backendType !== 'custom') {
    redirect('/metrics');
  }

  // The other tabs' data; the tuning routes reject non-custom metrics.
  const [requirements, tuning] = await Promise.all([
    prefetch(Capability.Requirement.READ, () =>
      fetchMetricLinkedRequirements(apiFactory, identifier)
    ),
    isCustomMetric(metric)
      ? prefetch(Capability.Metric.READ, () =>
          fetchMetricTuning(apiFactory, identifier)
        )
      : Promise.resolve(undefined),
  ]);

  return (
    <MetricDetailPageTabs
      metricId={identifier}
      initialMetric={JSON.parse(JSON.stringify(metric))}
      initialRequirements={requirements}
      initialTuning={tuning}
    />
  );
}
