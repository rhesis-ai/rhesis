import * as React from 'react';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import BehaviorDetailClient from './components/BehaviorDetailClient';
import type { UUID } from 'crypto';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  const { identifier } = await params;
  return {
    title: 'Behavior Details',
    description: `Details for Behavior ${identifier}`,
  };
}

export default async function BehaviorDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  const projectId = await getServerActiveProjectId();
  const client = new BehaviorClient(
    session.session_token,
    undefined,
    projectId
  );

  const behavior = await client.getBehaviorWithMetrics(identifier as UUID);

  if (!behavior) {
    throw new Error('Behavior not found');
  }

  const serializedBehavior = JSON.parse(JSON.stringify(behavior));

  return (
    <BehaviorDetailClient
      behavior={serializedBehavior}
      sessionToken={session.session_token}
      identifier={identifier}
    />
  );
}
