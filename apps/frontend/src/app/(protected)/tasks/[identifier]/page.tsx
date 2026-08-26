import * as React from 'react';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import TaskDetailClient from './components/TaskDetailClient';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function TaskDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const client = (await createServerApiFactory()).getTasksClient();

  let task;
  try {
    task = await client.getTask(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  return (
    <TaskDetailClient
      identifier={identifier}
      initialTask={JSON.parse(JSON.stringify(task))}
    />
  );
}
