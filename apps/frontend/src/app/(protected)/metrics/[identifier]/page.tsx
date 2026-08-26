import * as React from 'react';
import { redirect } from 'next/navigation';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import MetricDetailPageTabs from './MetricDetailPageTabs';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function MetricDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const client = (await createServerApiFactory()).getMetricsClient();

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

  return (
    <MetricDetailPageTabs
      metricId={identifier}
      initialMetric={JSON.parse(JSON.stringify(metric))}
    />
  );
}
