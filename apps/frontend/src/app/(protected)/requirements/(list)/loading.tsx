'use client';

import { useSession } from 'next-auth/react';
import type { UUID } from 'crypto';
import { SkeletonMode } from '@/components/loading/SkeletonMode';
import RequirementsClient from '../components/RequirementsClient';

/** The Requirements page itself, drawn as placeholders until its data arrives. */
export default function RequirementsLoading() {
  const { data: session } = useSession();
  return (
    <SkeletonMode>
      <RequirementsClient
        organizationId={session?.user?.organization_id as UUID}
        userId={session?.user?.id as UUID | undefined}
      />
    </SkeletonMode>
  );
}
