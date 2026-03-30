'use client';

import { useParams } from 'next/navigation';
import { MetricDetailView } from './MetricDetailView';

export default function MetricDetailPage() {
  const params = useParams();
  const metricId = params.identifier as string;
  return <MetricDetailView metricId={metricId} mode="page" />;
}
