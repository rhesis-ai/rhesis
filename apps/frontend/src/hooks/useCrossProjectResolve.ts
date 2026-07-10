'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ResolvedEntity } from '@/utils/api-client/resolve-client';
import { UUID_PATTERN } from '@/utils/entity-error-handler';

interface UseCrossProjectResolveResult {
  crossProjectData: ResolvedEntity | null;
  isResolving: boolean;
  resolveAttempted: boolean;
}

export function useCrossProjectResolve(
  entityType: string | undefined,
  entityId: string | undefined,
  enabled = true
): UseCrossProjectResolveResult {
  const { data: session } = useSession();
  const [crossProjectData, setCrossProjectData] =
    useState<ResolvedEntity | null>(null);
  const [resolveAttempted, setResolveAttempted] = useState(false);

  useEffect(() => {
    setCrossProjectData(null);
    setResolveAttempted(false);
  }, [entityType, entityId, enabled]);

  useEffect(() => {
    if (!enabled || !entityType || !entityId) {
      return;
    }

    if (!session?.session_token) {
      setResolveAttempted(true);
      return;
    }

    if (!UUID_PATTERN.test(entityId)) {
      setResolveAttempted(true);
      return;
    }

    let cancelled = false;
    const factory = new ApiClientFactory(session.session_token);
    const resolveClient = factory.getResolveClient();

    resolveClient
      .resolveEntity(entityType, entityId)
      .then(result => {
        if (!cancelled) {
          setCrossProjectData(result);
          setResolveAttempted(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setResolveAttempted(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, entityType, entityId, session?.session_token]);

  const isResolving =
    enabled &&
    !!entityType &&
    !!entityId &&
    UUID_PATTERN.test(entityId) &&
    !resolveAttempted &&
    !!session?.session_token;

  return {
    crossProjectData,
    isResolving,
    resolveAttempted: resolveAttempted || !session?.session_token,
  };
}
