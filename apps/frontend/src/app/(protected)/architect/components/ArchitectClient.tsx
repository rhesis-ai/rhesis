'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ArchitectSession } from '@/utils/api-client/architect-client';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
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

  // Reload sessions whenever the active project changes so the sidebar always
  // shows only sessions belonging to the current project. The backend already
  // filters by project via RLS (X-Project-Id header); we just need to re-fetch
  // when the project scope switches.
  useEffect(() => {
    const loadSessions = async () => {
      const client = getClient();
      if (!client) return;
      setIsLoadingSessions(true);
      try {
        const data = await client.getSessions();
        setSessions(data);

        const projectId = activeProject?.id;
        if (projectId) {
          const resumeSessionId = pickResumableSessionId(projectId, data);
          setActiveSessionId(resumeSessionId);
        } else {
          setActiveSessionId(null);
        }
      } catch (err) {
        console.error('Failed to load architect sessions:', err);
        setActiveSessionId(null);
      } finally {
        setIsLoadingSessions(false);
      }
    };
    loadSessions();
  }, [getClient, activeProject?.id]);

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
