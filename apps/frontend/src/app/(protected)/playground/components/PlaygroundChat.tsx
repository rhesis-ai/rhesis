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
  Snackbar,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import Tooltip from '@mui/material/Tooltip';
import { useSession } from 'next-auth/react';
import { usePlaygroundChat } from '@/hooks/usePlaygroundChat';
import MessageBubble, { MessageBubbleSkeleton } from './MessageBubble';
import TraceDrawer from '@/app/(protected)/traces/components/TraceDrawer';
import CreateTestFromConversationDrawer from './CreateTestFromConversationDrawer';
import { ConversationMessage } from '@/utils/api-client/interfaces/tests';

interface PlaygroundChatProps {
  /** The endpoint ID to chat with */
  endpointId: string;
  /** The project ID for trace viewing */
  projectId: string;
  /** Optional label shown in the header bar (e.g. "Chat 1") */
  label?: string;
  /** Callback when the close button in the header is clicked */
  onClose?: () => void;
  /** Callback to add a split pane (renders a "+" button in the top-right) */
  onSplit?: () => void;
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
  label,
  onClose,
  onSplit,
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
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  // Test creation drawer state
  const [testDrawerOpen, setTestDrawerOpen] = useState(false);
  const [testDrawerType, setTestDrawerType] = useState<
    'Single-Turn' | 'Multi-Turn'
  >('Multi-Turn');
  const [testDrawerMessages, setTestDrawerMessages] = useState<
    ConversationMessage[]
  >([]);

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

  const handleCreateMultiTurnTest = useCallback(() => {
    if (messages.length < 2) return;

    const conversationMessages = messages
      .filter(msg => !msg.isError)
      .map(msg => ({ role: msg.role, content: msg.content }));

    setTestDrawerMessages(conversationMessages);
    setTestDrawerType('Multi-Turn');
    setTestDrawerOpen(true);
  }, [messages]);

  const handleCreateSingleTurnTest = useCallback(
    (messageId: string) => {
      const messageIndex = messages.findIndex(m => m.id === messageId);
      if (messageIndex === -1) return;

      const userMessage = messages[messageIndex];
      const conversationMessages: ConversationMessage[] = [
        { role: userMessage.role, content: userMessage.content },
      ];

      // Include the next assistant message if available
      const nextMessage = messages[messageIndex + 1];
      if (
        nextMessage &&
        nextMessage.role === 'assistant' &&
        !nextMessage.isError
      ) {
        conversationMessages.push({
          role: nextMessage.role,
          content: nextMessage.content,
        });
      }

      setTestDrawerMessages(conversationMessages);
      setTestDrawerType('Single-Turn');
      setTestDrawerOpen(true);
    },
    [messages]
  );

  const handleTestCreated = useCallback(() => {
    setSnackbar({
      open: true,
      message: 'Test created successfully',
      severity: 'success',
    });
  }, []);

  return (
    <>
      <Paper
        elevation={1}
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: theme => theme.shape.borderRadius,
          overflow: 'hidden',
        }}
      >
        {/* Pane Header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: label ? 'space-between' : 'flex-end',
            px: 1.5,
            minHeight: theme => theme.spacing(4),
            bgcolor: 'action.hover',
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          {label && (
            <Typography
              variant="caption"
              color="text.secondary"
              fontWeight="medium"
            >
              {label}
            </Typography>
          )}
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {/* Create Multi-Turn Test Button */}
            <Tooltip
              title={
                messages.length < 2
                  ? 'Start a conversation to create a test'
                  : 'Create multi-turn test from conversation'
              }
            >
              <span>
                <IconButton
                  size="small"
                  onClick={handleCreateMultiTurnTest}
                  disabled={messages.length < 2 || isLoading}
                  sx={{ color: 'text.secondary', p: 0.25 }}
                >
                  <ScienceOutlinedIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            {onClose && (
              <IconButton
                size="small"
                onClick={onClose}
                sx={{ color: 'text.secondary', p: 0.25 }}
              >
                <CloseIcon fontSize="inherit" />
              </IconButton>
            )}
            {onSplit && (
              <Tooltip title="Add chat pane">
                <IconButton
                  size="small"
                  onClick={onSplit}
                  sx={{ color: 'text.secondary', p: 0.25 }}
                >
                  <AddIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

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
                  onCreateSingleTurnTest={handleCreateSingleTurnTest}
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
            {/* Reset Conversation Button */}
            {messages.length > 0 && (
              <Tooltip title="Reset conversation">
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
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
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
                  borderRadius: theme => theme.shape.borderRadius,
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

      {/* Create Test from Conversation Drawer */}
      {session?.session_token && (
        <CreateTestFromConversationDrawer
          open={testDrawerOpen}
          onClose={() => setTestDrawerOpen(false)}
          sessionToken={session.session_token}
          messages={testDrawerMessages}
          testType={testDrawerType}
          endpointId={endpointId}
          onSuccess={handleTestCreated}
        />
      )}

      {/* Snackbar for test creation feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
}
