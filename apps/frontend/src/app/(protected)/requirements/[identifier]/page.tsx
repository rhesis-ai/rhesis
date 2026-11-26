import * as React from 'react';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { entityErrorView } from '@/utils/entity-error-view';
import RequirementDetailClient from './components/RequirementDetailClient';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { fetchRequirementLinkedTests } from './components/linked-tests';
import type { UUID } from 'crypto';
import { requireSession } from '@/utils/require-session';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function RequirementDetailPage({ params }: PageProps) {
  await requireSession();

  const { identifier } = await params;
  // Server-side calls must go through createServerApiFactory: the session
  // object no longer exposes the access token (session.session_token is
  // always undefined post-BFF), and the factory also threads the active
  // project header.
  const apiFactory = await createServerApiFactory();
  const client = apiFactory.getRequirementClient();

  // Linked Tests tab; Linked Metrics already arrive on the requirement.
  // Only needs `identifier`, not the requirement itself.
  const linkedTestsPromise = prefetch(Capability.Test.READ, () =>
    fetchRequirementLinkedTests(apiFactory, identifier)
  );

  let requirement;
  try {
    requirement = await client.getRequirementWithMetrics(identifier as UUID);
  } catch (error) {
    const errorView = entityErrorView(error);
    if (errorView) return errorView;
    throw error;
  }

  const serializedRequirement = JSON.parse(JSON.stringify(requirement));

  const linkedTests = await linkedTestsPromise;

  return (
    <RequirementDetailClient
      requirement={serializedRequirement}
      identifier={identifier}
      initialLinkedTests={linkedTests}
    />
  );
}
