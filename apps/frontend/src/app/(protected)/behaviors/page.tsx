'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import BehaviorsClient from './components/BehaviorsClient';
import type { UUID } from 'crypto';

export default function BehaviorsPage() {
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
    <BehaviorsClient
      sessionToken={sessionToken}
      organizationId={organizationId}
      sessionStatus={status}
    />
  );
}
