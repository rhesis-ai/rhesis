'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ArchitectSession } from '@/utils/api-client/architect-client';
import ArchitectSidebar from './ArchitectSidebar';
import ArchitectChat from './ArchitectChat';
import ArchitectWelcome from './ArchitectWelcome';

export default function ArchitectClient() {
  const { data: session } = useSession();
  const [sessions, setSessions] = useState<ArchitectSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

  const getClient = useCallback(() => {
    if (!session?.session_token) return null;
    return new ApiClientFactory(session.session_token).getArchitectClient();
  }, [session?.session_token]);

  // Load sessions on mount
  useEffect(() => {
    const loadSessions = async () => {
      const client = getClient();
      if (!client) return;
      try {
        const data = await client.getSessions();
        setSessions(data);
      } catch (err) {
        console.error('Failed to load architect sessions:', err);
      } finally {
        setIsLoadingSessions(false);
      }
    };
    loadSessions();
  }, [getClient]);

  const handleNewSession = useCallback(async () => {
    const client = getClient();
    if (!client) return;
    try {
      const newSession = await client.createSession();
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  }, [getClient]);

  const handleNewSessionWithMessage = useCallback(
    async (message: string) => {
      const client = getClient();
      if (!client) return;
      try {
        const newSession = await client.createSession();
        setSessions(prev => [newSession, ...prev]);
        setPendingMessage(message);
        setActiveSessionId(newSession.id);
      } catch (err) {
        console.error('Failed to create session:', err);
      }
    },
    [getClient]
  );

  const handleSelectSession = useCallback(
    async (id: string) => {
      setActiveSessionId(id);
    },
    []
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
        }
      } catch (err) {
        console.error('Failed to delete session:', err);
      }
    },
    [getClient, activeSessionId]
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
  }, []);

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
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
          />
        ) : (
          <ArchitectWelcome
            onSubmit={handleNewSessionWithMessage}
          />
        )}
      </Box>
    </Box>
  );
}
