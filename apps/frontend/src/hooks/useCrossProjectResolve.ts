'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ResolvedEntity } from '@/utils/api-client/resolve-client';
import { UUID_PATTERN } from '@/utils/entity-error-handler';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface UseCrossProjectResolveResult {
  crossProjectData: ResolvedEntity | null;
  isResolving: boolean;
  resolveAttempted: boolean;
  resolveError: unknown;
  retryResolve: () => void;
}

export function useCrossProjectResolve(
  entityType: string | undefined,
  entityId: string | undefined,
  enabled = true
): UseCrossProjectResolveResult {
  const { status } = useSession();
  const [crossProjectData, setCrossProjectData] =
    useState<ResolvedEntity | null>(null);
  const [resolveAttempted, setResolveAttempted] = useState(false);
  const [resolveError, setResolveError] = useState<unknown>(null);
  const [retryCount, setRetryCount] = useState(0);
  const requestIdRef = useRef(0);

  const retryResolve = useCallback(() => {
    setResolveAttempted(false);
    setResolveError(null);
    setRetryCount(count => count + 1);
  }, []);

  useEffect(() => {
    setCrossProjectData(null);
    setResolveAttempted(false);
    setResolveError(null);
  }, [entityType, entityId, enabled]);

  useEffect(() => {
    if (!enabled || !entityType || !entityId) {
      return;
    }

    if (!isAuthenticated(status)) {
      setResolveAttempted(true);
      return;
    }

    if (!UUID_PATTERN.test(entityId)) {
      setResolveAttempted(true);
      return;
    }

    const requestId = ++requestIdRef.current;
    const factory = new ApiClientFactory();
    const resolveClient = factory.getResolveClient();

    resolveClient
      .resolveEntity(entityType, entityId)
      .then(result => {
        if (requestIdRef.current !== requestId) {
          return;
        }
        setCrossProjectData(result);
        setResolveError(null);
        setResolveAttempted(true);
      })
      .catch(error => {
        if (requestIdRef.current !== requestId) {
          return;
        }
        setResolveError(error);
        setResolveAttempted(true);
      });

    return () => {
      requestIdRef.current += 1;
    };
  }, [enabled, entityType, entityId, retryCount, status]);

  const isResolving =
    enabled &&
    !!entityType &&
    !!entityId &&
    UUID_PATTERN.test(entityId) &&
    !resolveAttempted &&
    isAuthenticated(status);

  return {
    crossProjectData,
    isResolving,
    resolveAttempted: resolveAttempted || !isAuthenticated(status),
    resolveError,
    retryResolve,
  };
}
