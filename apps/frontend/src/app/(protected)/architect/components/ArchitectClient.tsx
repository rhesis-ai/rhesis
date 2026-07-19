'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ArchitectSession } from '@/utils/api-client/architect-client';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import {
  clearResumeHint,
  pickResumableSessionId,
  writeResumeHint,
} from '@/utils/architect-resume';
import ArchitectSidebar from './ArchitectSidebar';
import ArchitectChat from './ArchitectChat';
import ArchitectWelcome from './ArchitectWelcome';

export default function ArchitectClient() {
  const { data: session } = useSession();
  const { activeProject } = useActiveProject();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Architect.READ
  );
  const [sessions, setSessions] = useState<ArchitectSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  const getClient = useCallback(() => {
    if (!session?.session_token) return null;
    return new ApiClientFactory(session.session_token).getArchitectClient();
  }, [session?.session_token]);

  const touchResumeHint = useCallback(
    (sessionId: string) => {
      if (activeProject?.id) {
        writeResumeHint(activeProject.id, sessionId);
      }
    },
    [activeProject?.id]
  );

  const clearSessionQueryParam = useCallback(() => {
    if (!searchParams.has('session')) return;
    const params = new URLSearchParams(searchParams.toString());
    params.delete('session');
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  // Reload sessions whenever the active project changes so the sidebar always
  // shows only sessions belonging to the current project. The backend already
  // filters by project via RLS (X-Project-Id header); we just need to re-fetch
  // when the project scope switches.
  // Prefer ?session= over the resume hint (contextual handoffs from Insights etc.).
  useEffect(() => {
    const loadSessions = async () => {
      if (permsLoading || !canRead) return;
      const client = getClient();
      if (!client) return;
      setIsLoadingSessions(true);
      setActiveSessionId(null);
      setSessions([]);
      try {
        const data = await client.getSessions();
        let nextSessions = data;
        const sessionFromQuery = searchParams.get('session');

        if (sessionFromQuery) {
          if (!data.some(s => s.id === sessionFromQuery)) {
            try {
              const detail = await client.getSession(sessionFromQuery);
              nextSessions = [
                detail,
                ...data.filter(s => s.id !== detail.id),
              ];
            } catch (err) {
              console.error('Failed to load session from query:', err);
            }
          }
          setSessions(nextSessions);
          const exists = nextSessions.some(s => s.id === sessionFromQuery);
          setActiveSessionId(exists ? sessionFromQuery : null);
          if (exists) {
            touchResumeHint(sessionFromQuery);
          }
          clearSessionQueryParam();
        } else {
          setSessions(nextSessions);
          const projectId = activeProject?.id;
          if (projectId) {
            const resumeSessionId = pickResumableSessionId(projectId, data);
            setActiveSessionId(resumeSessionId);
          } else {
            setActiveSessionId(null);
          }
        }
      } catch (err) {
        console.error('Failed to load architect sessions:', err);
        setActiveSessionId(null);
      } finally {
        setIsLoadingSessions(false);
      }
    };
    loadSessions();
    // Intentionally omit searchParams from deps after first load for a given
    // project — clearing ?session= must not re-trigger a full reload loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- project/token drive reload
  }, [getClient, activeProject?.id, permsLoading, canRead]);

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
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      touchResumeHint(newSession.id);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  }, [getClient, touchResumeHint]);

  const handleNewSessionWithMessage = useCallback(
    async (message: string) => {
      const client = getClient();
      if (!client) return;
      // Drop the welcome screen immediately — no flicker during the API call.
      setIsCreatingSession(true);
      try {
        const newSession = await client.createSession();
        setSessions(prev => [newSession, ...prev]);
        setPendingMessage(message);
        setActiveSessionId(newSession.id);
        touchResumeHint(newSession.id);
      } catch (err) {
        console.error('Failed to create session:', err);
        setIsCreatingSession(false);
      }
    },
    [getClient, touchResumeHint]
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
        setSessions(prev => prev.filter(s => s.id !== id));
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
    [getClient, activeSessionId, activeProject?.id]
  );

  const handleSessionTitleUpdate = useCallback(
    (sessionId: string, title: string) => {
      setSessions(prev =>
        prev.map(s => (s.id === sessionId ? { ...s, title } : s))
      );
    },
    []
  );

  const handleInitialMessageSent = useCallback(() => {
    setPendingMessage(null);
    if (activeSessionId) {
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
            sessionToken={session?.session_token}
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
