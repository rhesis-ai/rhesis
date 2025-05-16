'use client';

import * as React from 'react';
import dynamic from 'next/dynamic';

const MetricWorkflowSection = dynamic(
  () => import('./MetricWorkflowSection'),
  { ssr: false }
);

interface ClientWorkflowWrapperProps {
  metricId: string;
  status: string;
  sessionToken: string;
}

export default function ClientWorkflowWrapper(props: ClientWorkflowWrapperProps) {
  return <MetricWorkflowSection {...props} />;
} 