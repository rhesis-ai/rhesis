import * as React from 'react';
import { Metadata } from 'next';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import RequirementDetailClient from './components/RequirementDetailClient';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { fetchRequirementLinkedTests } from './components/linked-tests';
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
    title: 'Requirement Details',
    description: `Details for Requirement ${identifier}`,
  };
}

export default async function RequirementDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;
  // Server-side calls must go through createServerApiFactory: the session
  // object no longer exposes the access token (session.session_token is
  // always undefined post-BFF), and the factory also threads the active
  // project header.
  const apiFactory = await createServerApiFactory();
  const client = apiFactory.getRequirementClient();

  let requirement;
  try {
    requirement = await client.getRequirementWithMetrics(identifier as UUID);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  const serializedRequirement = JSON.parse(JSON.stringify(requirement));

  // Linked Tests tab; Linked Metrics already arrive on the requirement.
  const linkedTests = await prefetch(Capability.Test.READ, () =>
    fetchRequirementLinkedTests(apiFactory, identifier)
  );

  return (
    <RequirementDetailClient
      requirement={serializedRequirement}
      identifier={identifier}
      initialLinkedTests={linkedTests}
    />
  );
}
