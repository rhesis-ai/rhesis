'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Alert,
  CircularProgress,
  Chip,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import Tooltip from '@mui/material/Tooltip';
import { useSession } from 'next-auth/react';
import { useArchitectChat, ArchitectChatMessage } from '@/hooks/useArchitectChat';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ArchitectMessageBubble from './ArchitectMessageBubble';
import StreamingIndicator from './StreamingIndicator';
import PlanDisplay from './PlanDisplay';

interface ArchitectChatProps {
  sessionId: string | null;
  sessionToken?: string;
  onSessionTitleUpdate?: (sessionId: string, title: string) => void;
  initialMessage?: string | null;
  onInitialMessageSent?: () => void;
}

const SUGGESTED_PROMPTS = [
  'I need safety and fairness tests for my LLM application',
  'Help me test for prompt injection vulnerabilities',
  'Create a comprehensive test suite for a RAG pipeline',
];

export default function ArchitectChat({
  sessionId,
  sessionToken,
  onSessionTitleUpdate,
  initialMessage,
  onInitialMessageSent,
}: ArchitectChatProps) {
  const { data: authSession } = useSession();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    isLoading,
    error,
    isConnected,
    streamingState,
    currentMode,
    currentPlan,
    sendMessage,
    setMessages,
  } = useArchitectChat({ sessionId });

  const [inputValue, setInputValue] = useState('');

  // Load existing messages when session changes
  useEffect(() => {
    if (!sessionId || !sessionToken) return;

    const loadMessages = async () => {
      try {
        const client = new ApiClientFactory(
          sessionToken
        ).getArchitectClient();
        const session = await client.getSession(sessionId);

        if (session.messages?.length) {
          const loaded: ArchitectChatMessage[] = session.messages
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .map(m => ({
              id: m.id,
              role: m.role as 'user' | 'assistant',
              content: m.content || '',
              timestamp: new Date(m.created_at || Date.now()),
            }));
          setMessages(loaded);
        } else {
          setMessages([]);
        }
      } catch (err) {
        console.error('Failed to load messages:', err);
      }
    };

    loadMessages();
  }, [sessionId, sessionToken, setMessages]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, streamingState]);

  // Auto-send initial message when connection is ready
  const initialMessageSentRef = useRef<string | null>(null);
  useEffect(() => {
    if (
      initialMessage &&
      isConnected &&
      sessionId &&
      initialMessageSentRef.current !== initialMessage
    ) {
      initialMessageSentRef.current = initialMessage;
      sendMessage(initialMessage);
      onInitialMessageSent?.();
    }
  }, [initialMessage, isConnected, sessionId, sendMessage, onInitialMessageSent]);

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading) inputRef.current?.focus();
  }, [isLoading]);

  const handleSend = useCallback(() => {
    if (inputValue.trim() && !isLoading) {
      sendMessage(inputValue);
      setInputValue('');
    }
  }, [inputValue, isLoading, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestedPrompt = (prompt: string) => {
    if (!isLoading) {
      sendMessage(prompt);
    }
  };

  if (!sessionId) {
    return null;
  }

  return (
    <Paper
      elevation={0}
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        borderRadius: 0,
      }}
    >
      {/* Header with mode badge */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          borderBottom: 1,
          borderColor: 'divider',
          minHeight: 40,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip
            label={currentMode}
            size="small"
            color={
              currentMode === 'discovery'
                ? 'info'
                : currentMode === 'planning'
                  ? 'warning'
                  : currentMode === 'creating'
                    ? 'success'
                    : 'default'
            }
            variant="outlined"
          />
        </Box>
        {!isConnected && (
          <Typography variant="caption" color="warning.main">
            Reconnecting...
          </Typography>
        )}
      </Box>

      {/* Messages area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 3,
          bgcolor: 'background.default',
        }}
      >
        {messages.length === 0 && !isLoading ? (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              gap: 3,
            }}
          >
            <Typography variant="body1" color="text.secondary">
              What would you like to test?
            </Typography>
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 1,
                justifyContent: 'center',
                maxWidth: 600,
              }}
            >
              {SUGGESTED_PROMPTS.map(prompt => (
                <Chip
                  key={prompt}
                  label={prompt}
                  variant="outlined"
                  onClick={() => handleSuggestedPrompt(prompt)}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          </Box>
        ) : (
          <>
            {messages.map(message => (
              <ArchitectMessageBubble
                key={message.id}
                message={message}
                userName={authSession?.user?.name || undefined}
                userPicture={authSession?.user?.picture || undefined}
              />
            ))}

            {/* Streaming indicator */}
            {isLoading && <StreamingIndicator state={streamingState} />}

            {/* Scroll anchor */}
            <div ref={messagesEndRef} />
          </>
        )}
      </Box>

      {/* Plan display */}
      {currentPlan && <PlanDisplay plan={currentPlan} />}

      {/* Error alert */}
      {error && !isLoading && (
        <Alert severity="error" sx={{ mx: 2, mb: 1 }}>
          {error}
        </Alert>
      )}

      {/* Input area */}
      <Box
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            inputRef={inputRef}
            fullWidth
            multiline
            maxRows={4}
            placeholder={
              isConnected
                ? 'Describe what you want to test...'
                : 'Waiting for connection...'
            }
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!isConnected || isLoading}
            size="small"
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: theme => theme.shape.borderRadius,
              },
            }}
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={!inputValue.trim() || !isConnected || isLoading}
            sx={{
              width: theme => theme.spacing(5),
              height: theme => theme.spacing(5),
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              '&:hover': { bgcolor: 'primary.dark' },
              '&:disabled': {
                bgcolor: 'action.disabledBackground',
                color: 'action.disabled',
              },
            }}
          >
            {isLoading ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <SendIcon />
            )}
          </IconButton>
        </Box>
      </Box>
    </Paper>
  );
}
