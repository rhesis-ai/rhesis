import * as React from 'react';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import TaskDetailClient from './components/TaskDetailClient';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function TaskDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const apiFactory = await createServerApiFactory();
  const client = apiFactory.getTasksClient();

  let task;
  try {
    task = await client.getTask(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  // Comments tab, so it opens with content in place.
  const comments = await prefetch(Capability.Comment.READ, () =>
    apiFactory.getCommentsClient().getComments('Task', identifier)
  );

  return (
    <TaskDetailClient
      identifier={identifier}
      initialTask={JSON.parse(JSON.stringify(task))}
      initialComments={comments}
    />
  );
}
