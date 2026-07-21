import * as React from 'react';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
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

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  // Server-side calls must go through createServerApiFactory: the session
  // object no longer exposes the access token (session.session_token is
  // always undefined post-BFF), and the factory also threads the active
  // project header.
  const client = (await createServerApiFactory()).getBehaviorClient();

  let behavior;
  try {
    behavior = await client.getBehaviorWithMetrics(identifier as UUID);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const serializedBehavior = JSON.parse(JSON.stringify(behavior));

  return (
    <BehaviorDetailClient
      behavior={serializedBehavior}
      identifier={identifier}
    />
  );
}
