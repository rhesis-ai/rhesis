'use client';

import * as React from 'react';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricUpdate } from '@/utils/api-client/interfaces/metric';

interface MetricWorkflowSectionProps {
  metricId: string;
  status: string;
  sessionToken: string;
}

export default function MetricWorkflowSection({ 
  metricId,
  status,
  sessionToken
}: MetricWorkflowSectionProps) {
  const clientFactory = React.useMemo(() => new ApiClientFactory(sessionToken), [sessionToken]);

  const handleUpdateEntity = React.useCallback(async (updateData: MetricUpdate, fieldName: string) => {
    try {
      const client = clientFactory.getMetricsClient();
      await client.updateMetric(metricId, updateData);
    } catch (error) {
      console.error('Error updating metric:', error);
      throw error;
    }
  }, [clientFactory, metricId]);

  return (
    <BaseWorkflowSection
      title="Workflow"
      status={status}
      clientFactory={clientFactory}
      entityId={metricId}
      entityType="Metric"
      onUpdateEntity={handleUpdateEntity}
      showPriority={false}
    />
  );
} 