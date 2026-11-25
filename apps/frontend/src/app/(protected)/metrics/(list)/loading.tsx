'use client';

import { useSession } from 'next-auth/react';
import type { UUID } from 'crypto';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import MetricsClientComponent from '../components/MetricsClient';

/** The Metrics page itself, drawn as placeholders until its data arrives. */
export default function MetricsLoading() {
  const { data: session } = useSession();
  return (
    <SkeletonMode>
      <MetricsClientComponent
        organizationId={session?.user?.organization_id as UUID}
      />
    </SkeletonMode>
  );
}
