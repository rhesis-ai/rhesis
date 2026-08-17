'use client';

import * as React from 'react';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { PageLayout } from '@/components/layout/PageLayout';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import JobsGrid from './components/JobsGrid';

export default function JobsPage() {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Job.READ
  );

  useDocumentTitle('Jobs');

  if (permsLoading) {
    return <PageLoadingState />;
  }

  if (!canRead) {
    return <AccessDenied resource="jobs" />;
  }

  return (
    <PageLayout
      title="Jobs"
      description="Background work the platform is doing, and what it logged along the way."
      breadcrumbs={[{ label: 'Jobs' }]}
    >
      <JobsGrid />
    </PageLayout>
  );
}
