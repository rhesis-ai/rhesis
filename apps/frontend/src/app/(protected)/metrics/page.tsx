'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';

export default function MetricsPage() {
  const { data: session, status } = useSession();
  const canRead = useCan(Capability.Metric.READ);

  const sessionToken = React.useMemo(
    () => session?.session_token ?? '',
    [session?.session_token]
  );
  const organizationId = React.useMemo(
    () => session?.user?.organization_id as UUID,
    [session?.user?.organization_id]
  );

  if (!canRead) return <AccessDenied resource="metrics" />;

  return (
    <MetricsClientComponent
      sessionToken={sessionToken}
      organizationId={organizationId}
      sessionStatus={status}
    />
  );
}
