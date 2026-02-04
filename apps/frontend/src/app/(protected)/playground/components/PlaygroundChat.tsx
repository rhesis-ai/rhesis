'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Alert,
  CircularProgress,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useSession } from 'next-auth/react';
import { usePlaygroundChat } from '@/hooks/usePlaygroundChat';
import MessageBubble, { MessageBubbleSkeleton } from './MessageBubble';
import TraceDrawer from '@/app/(protected)/traces/components/TraceDrawer';

interface PlaygroundChatProps {
  /** The endpoint ID to chat with */
  endpointId: string;
  /** The project ID for trace viewing */
  projectId: string;
}

/**
 * PlaygroundChat Component
 *
 * The main chat interface for the playground.
 * Handles message input, display, and trace viewing.
 */
export default function PlaygroundChat({
  endpointId,
  projectId,
}: PlaygroundChatProps) {
  const { data: session } = useSession();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    isLoading,
    error,
    isConnected,
    sendMessage,
    clearMessages,
  } = usePlaygroundChat({ endpointId });

  const [inputValue, setInputValue] = useState('');
  const [traceDrawerOpen, setTraceDrawerOpen] = useState(false);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus input on mount and when response arrives (isLoading becomes false)
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  const handleSend = () => {
    if (inputValue.trim() && !isLoading) {
      sendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleViewTrace = (traceId: string) => {
    setSelectedTraceId(traceId);
    setTraceDrawerOpen(true);
  };

  const handleCloseTraceDrawer = () => {
    setTraceDrawerOpen(false);
    setSelectedTraceId(null);
  };

  return (
    <>
      <Paper
        elevation={1}
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        {/* Messages Area */}
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
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Send a message to start the conversation
              </Typography>
            </Box>
          ) : (
            <>
              {messages.map(message => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onViewTrace={handleViewTrace}
                />
              ))}

              {/* Loading indicator */}
              {isLoading && <MessageBubbleSkeleton />}

              {/* Scroll anchor */}
              <div ref={messagesEndRef} />
            </>
          )}
        </Box>

        {/* Error Alert */}
        {error && !isLoading && (
          <Alert severity="error" sx={{ mx: 2, mb: 1 }}>
            {error}
          </Alert>
        )}

        {/* Connection Warning */}
        {!isConnected && (
          <Alert severity="warning" sx={{ mx: 2, mb: 1 }}>
            WebSocket disconnected. Attempting to reconnect...
          </Alert>
        )}

        {/* Input Area */}
        <Box
          sx={{
            p: 2,
            borderTop: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
            {/* Clear Button */}
            {messages.length > 0 && (
              <IconButton
                size="small"
                onClick={clearMessages}
                disabled={isLoading}
                sx={{
                  color: 'text.secondary',
                  '&:hover': {
                    color: 'error.main',
                  },
                }}
              >
                <DeleteOutlineIcon />
              </IconButton>
            )}

            {/* Input Field */}
            <TextField
              inputRef={inputRef}
              fullWidth
              multiline
              maxRows={4}
              placeholder={
                isConnected
                  ? 'Type your message...'
                  : 'Waiting for connection...'
              }
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!isConnected || isLoading}
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 3,
                },
              }}
            />

            {/* Send Button */}
            <IconButton
              color="primary"
              onClick={handleSend}
              disabled={!inputValue.trim() || !isConnected || isLoading}
              sx={{
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                '&:hover': {
                  bgcolor: 'primary.dark',
                },
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

      {/* Trace Drawer */}
      {session?.session_token && (
        <TraceDrawer
          open={traceDrawerOpen}
          onClose={handleCloseTraceDrawer}
          traceId={selectedTraceId}
          projectId={projectId}
          sessionToken={session.session_token}
        />
      )}
    </>
  );
}
