'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';

export default function MetricsPage() {
  const { data: session, status } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Metric.READ
  );

  const organizationId = React.useMemo(
    () => session?.user?.organization_id as UUID,
    [session?.user?.organization_id]
  );

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="metrics" />;

  return (
    <MetricsClientComponent
      organizationId={organizationId}
      sessionStatus={status}
    />
  );
}
