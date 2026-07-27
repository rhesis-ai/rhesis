'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ArchitectSession } from '@/utils/api-client/architect-client';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { architectSessionKeys } from '@/constants/query-keys';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import {
  clearResumeHint,
  pickResumableSessionId,
  writeResumeHint,
} from '@/utils/architect-resume';
import {
  clearPendingHandoffMessage,
  peekPendingHandoffMessage,
} from '@/utils/architect-handoff';
import ArchitectSidebar from './ArchitectSidebar';
import ArchitectChat from './ArchitectChat';
import ArchitectWelcome from './ArchitectWelcome';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

export default function ArchitectClient() {
  const { status } = useSession();
  const userScope = useUserScope();
  const queryClient = useQueryClient();
  const { activeProject } = useActiveProject();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Architect.READ
  );
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  const projectKey = activeProject?.id ?? '';
  const sessionsQueryKey = architectSessionKeys.list(userScope, projectKey);

  const updateSessions = useCallback(
    (updater: (prev: ArchitectSession[]) => ArchitectSession[]) => {
      queryClient.setQueryData<ArchitectSession[]>(sessionsQueryKey, prev =>
        updater(prev ?? [])
      );
    },
    [queryClient, sessionsQueryKey]
  );

  // react-query dedupes Strict Mode remounts and project-scoped refetches.
  const { data: sessions = [], isLoading: isLoadingSessions } = useQuery({
    queryKey: sessionsQueryKey,
    queryFn: () => new ApiClientFactory().getArchitectClient().getSessions(),
    enabled:
      !permsLoading && canRead && isAuthenticated(status) && !!userScope,
    staleTime: 30_000,
  });

  const getClient = useCallback(() => {
    if (!isAuthenticated(status)) return null;
    return new ApiClientFactory().getArchitectClient();
  }, [status]);

  const touchResumeHint = useCallback(
    (sessionId: string) => {
      if (activeProject?.id) {
        writeResumeHint(activeProject.id, sessionId);
      }
    },
    [activeProject?.id]
  );

  const sessionFromQuery = searchParams.get('session');

  const clearSessionQueryParam = useCallback(() => {
    if (!searchParams.has('session')) return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete('session');
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  // When the project scope changes (or the list first resolves), clear / resume
  // selection. Skip while a ?session= handoff is pending — that effect wins.
  const resumeForProjectRef = useRef<string | null>(null);
  useEffect(() => {
    if (sessionFromQuery) return;

    // Project switched — drop the previous selection until the new list resolves.
    if (resumeForProjectRef.current !== projectKey) {
      setActiveSessionId(null);
    }

    if (permsLoading || !canRead || isLoadingSessions) return;
    if (resumeForProjectRef.current === projectKey) return;
    resumeForProjectRef.current = projectKey;

    if (projectKey) {
      setActiveSessionId(pickResumableSessionId(projectKey, sessions));
    } else {
      setActiveSessionId(null);
    }
    // sessions read once when the project key first resolves — intentionally
    // not a dep, so title/create/delete cache writes don't re-run resume.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectKey, permsLoading, canRead, isLoadingSessions, sessionFromQuery]);

  // Prefer ?session= over resume (contextual handoffs). Separate from the list
  // reload so in-app navigations to /architect?session= still work without a
  // remount (peqy).
  useEffect(() => {
    if (!sessionFromQuery || permsLoading || !canRead) return;

    let cancelled = false;

    const selectFromQuery = async () => {
      const client = getClient();
      if (!client) return;

      // Contextual handoffs (e.g. Insights → Summarize) stash their first
      // message under the session id instead of starting the turn on the
      // backend. Pick it up here and route it through the same auto-send path
      // the welcome screen uses, so the Architect starts working as soon as
      // this tab is connected — no lost events, no need for a manual "go".
      // Peek (don't remove) so the prompt bubble renders immediately while the
      // storage entry survives a failed getSession for a retry. It is removed
      // only once the message is actually sent (handleInitialMessageSent).
      const pendingHandoff = peekPendingHandoffMessage(sessionFromQuery);
      if (pendingHandoff) {
        setPendingMessage(pendingHandoff);
      }

      setActiveSessionId(sessionFromQuery);
      touchResumeHint(sessionFromQuery);
      resumeForProjectRef.current = projectKey;

      const alreadyListed = sessions.some(s => s.id === sessionFromQuery);
      if (!alreadyListed) {
        try {
          const detail = await client.getSession(sessionFromQuery);
          if (cancelled) return;
          updateSessions(prev => [
            detail,
            ...prev.filter(s => s.id !== detail.id),
          ]);
        } catch (err) {
          console.error('Failed to load session from query:', err);
          if (!cancelled) {
            setActiveSessionId(null);
            // Leave the storage entry in place (peek did not remove it) so a
            // reload can retry; just drop the in-memory pending message so it
            // cannot leak into another session.
            setPendingMessage(null);
          }
          return;
        }
      }

      clearSessionQueryParam();
    };

    selectFromQuery();
    return () => {
      cancelled = true;
    };
    // sessions intentionally omitted — we only need the id from the URL;
    // re-running on every list change would clear the param twice.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- query-driven select
  }, [
    sessionFromQuery,
    permsLoading,
    canRead,
    getClient,
    touchResumeHint,
    clearSessionQueryParam,
    projectKey,
    updateSessions,
  ]);

  // Bump last-activity when navigating away mid-conversation.
  useEffect(() => {
    const projectId = activeProject?.id;
    const sessionId = activeSessionId;
    return () => {
      if (projectId && sessionId) {
        writeResumeHint(projectId, sessionId);
      }
    };
  }, [activeProject?.id, activeSessionId]);

  const handleNewSession = useCallback(async () => {
    const client = getClient();
    if (!client) return;
    try {
      const newSession = await client.createSession();
      updateSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      touchResumeHint(newSession.id);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  }, [getClient, touchResumeHint, updateSessions]);

  const handleNewSessionWithMessage = useCallback(
    async (message: string) => {
      const client = getClient();
      if (!client) return;
      // Drop the welcome screen immediately — no flicker during the API call.
      setIsCreatingSession(true);
      try {
        const newSession = await client.createSession();
        updateSessions(prev => [newSession, ...prev]);
        setPendingMessage(message);
        setActiveSessionId(newSession.id);
        touchResumeHint(newSession.id);
      } catch (err) {
        console.error('Failed to create session:', err);
        setIsCreatingSession(false);
      }
    },
    [getClient, touchResumeHint, updateSessions]
  );

  const handleSelectSession = useCallback(
    (id: string) => {
      setActiveSessionId(id);
      touchResumeHint(id);
    },
    [touchResumeHint]
  );

  const handleDeleteSession = useCallback(
    async (id: string) => {
      const client = getClient();
      if (!client) return;
      try {
        await client.deleteSession(id);
        updateSessions(prev => prev.filter(s => s.id !== id));
        if (activeSessionId === id) {
          setActiveSessionId(null);
          if (activeProject?.id) {
            clearResumeHint(activeProject.id);
          }
        }
      } catch (err) {
        console.error('Failed to delete session:', err);
      }
    },
    [getClient, activeSessionId, activeProject?.id, updateSessions]
  );

  const handleSessionTitleUpdate = useCallback(
    (sessionId: string, title: string) => {
      updateSessions(prev =>
        prev.map(s => (s.id === sessionId ? { ...s, title } : s))
      );
    },
    [updateSessions]
  );

  const handleInitialMessageSent = useCallback(() => {
    setPendingMessage(null);
    if (activeSessionId) {
      // Remove the stashed handoff message only now that it has been sent, so
      // a reload cannot resend it. No-op for welcome-screen sessions (no entry).
      clearPendingHandoffMessage(activeSessionId);
      touchResumeHint(activeSessionId);
    }
  }, [activeSessionId, touchResumeHint]);

  const handleUserActivity = useCallback(() => {
    if (activeSessionId) {
      touchResumeHint(activeSessionId);
    }
  }, [activeSessionId, touchResumeHint]);

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="architect sessions" />;

  return (
    <Box
      sx={{
        display: 'flex',
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <ArchitectSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        isLoading={isLoadingSessions}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(prev => !prev)}
        onNewSession={handleNewSession}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
      />
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {activeSessionId ? (
          <ArchitectChat
            sessionId={activeSessionId}
            onSessionTitleUpdate={handleSessionTitleUpdate}
            initialMessage={pendingMessage}
            onInitialMessageSent={handleInitialMessageSent}
            onUserActivity={handleUserActivity}
            sessionProjectId={
              sessions.find(s => s.id === activeSessionId)?.project_id
            }
          />
        ) : !isCreatingSession ? (
          <ArchitectWelcome onSubmit={handleNewSessionWithMessage} />
        ) : null}
      </Box>
    </Box>
  );
}
