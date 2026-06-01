'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import MetricsClientComponent from './components/MetricsClient';
import type { UUID } from 'crypto';

export default function MetricsPage() {
  const { data: session, status } = useSession();

  const sessionToken = React.useMemo(
    () => session?.session_token ?? '',
    [session?.session_token]
  );
  const organizationId = React.useMemo(
    () => session?.user?.organization_id as UUID,
    [session?.user?.organization_id]
  );

  return (
    <MetricsClientComponent
      sessionToken={sessionToken}
      organizationId={organizationId}
      sessionStatus={status}
    />
  );
}
