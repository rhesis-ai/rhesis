import * as React from 'react';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { entityErrorView } from '@/utils/entity-error-view';
import JobDetailClient from './components/JobDetailClient';
import { requireSession } from '@/utils/require-session';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function JobDetailPage({ params }: PageProps) {
  await requireSession();

  const { identifier } = await params;
  const client = (await createServerApiFactory()).getJobsClient();

  // Activity fails open: the job still renders and the client fetches it.
  const [jobResult, activityResult] = await Promise.allSettled([
    client.getJob(identifier),
    client.getJobActivity(identifier),
  ]);
  if (jobResult.status === 'rejected') {
    const errorView = entityErrorView(jobResult.reason);
    if (errorView) return errorView;
    throw jobResult.reason;
  }
  const activity =
    activityResult.status === 'fulfilled' ? activityResult.value : undefined;

  return (
    <JobDetailClient
      jobId={identifier}
      initialJob={JSON.parse(JSON.stringify(jobResult.value))}
      initialActivity={
        activity ? JSON.parse(JSON.stringify(activity)) : undefined
      }
    />
  );
}
