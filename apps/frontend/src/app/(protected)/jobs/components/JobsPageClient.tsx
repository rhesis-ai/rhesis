'use client';

import * as React from 'react';
import { PageLayout } from '@/components/layout/PageLayout';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import JobsGrid from './JobsGrid';
import { jobsList } from './list';
import type { Job } from '@/utils/api-client/interfaces/job';
import { PAGE_HEADERS } from '@/constants/page-headers';

interface JobsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Job[];
  initialTotalCount?: number;
}

export default function JobsPageClient({
  initialData,
  initialTotalCount = 0,
}: JobsPageClientProps) {
  const gate = useListAuthGate(jobsList);

  useDocumentTitle('Jobs');

  if (!gate.ready) return gate.node;

  return (
    <PageLayout
      title={PAGE_HEADERS.jobs.title}
      description={PAGE_HEADERS.jobs.description}
      breadcrumbs={[]}
    >
      <JobsGrid
        initialData={initialData}
        initialTotalCount={initialTotalCount}
      />
    </PageLayout>
  );
}
