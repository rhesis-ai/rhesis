import * as React from 'react';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import JobDetailClient from './components/JobDetailClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function JobDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const client = (await createServerApiFactory()).getJobsClient();

  // Activity fails open: the job still renders and the client fetches it.
  const [jobResult, activityResult] = await Promise.allSettled([
    client.getJob(identifier),
    client.getJobActivity(identifier),
  ]);
  if (jobResult.status === 'rejected') {
    notFoundIfEntityMissing(jobResult.reason);
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
