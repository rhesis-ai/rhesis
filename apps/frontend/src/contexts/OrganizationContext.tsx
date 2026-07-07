'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Organization } from '@/utils/api-client/interfaces/organization';

interface OrganizationContextValue {
  organization: Organization | null;
  refresh: () => Promise<void>;
}

const OrganizationContext = createContext<OrganizationContextValue>({
  organization: null,
  refresh: async () => {},
});

export function OrganizationProvider({
  children,
  initialOrganization = null,
}: {
  children: React.ReactNode;
  initialOrganization?: Organization | null;
}) {
  const { data: session } = useSession();
  const [organization, setOrganization] = useState<Organization | null>(
    initialOrganization
  );

  const refresh = useCallback(async () => {
    if (!session?.session_token || !session?.user?.organization_id) return;
    try {
      const org = await new ApiClientFactory(session.session_token)
        .getOrganizationsClient()
        .getOrganization(session.user.organization_id);
      setOrganization(org);
    } catch {
      // leave stale data in place; callers handle their own error state
    }
  }, [session?.session_token, session?.user?.organization_id]);

  // If the server-rendered organization was unavailable (null) but a session is
  // now present, fetch it client-side rather than leaving the page stuck on a
  // hard "No organization information available" state. Runs once per
  // session-ready transition (organization becomes non-null → condition false).
  useEffect(() => {
    if (
      !organization &&
      session?.session_token &&
      session?.user?.organization_id
    ) {
      void refresh();
    }
  }, [
    organization,
    session?.session_token,
    session?.user?.organization_id,
    refresh,
  ]);

  return (
    <OrganizationContext.Provider value={{ organization, refresh }}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization(): OrganizationContextValue {
  return useContext(OrganizationContext);
}
