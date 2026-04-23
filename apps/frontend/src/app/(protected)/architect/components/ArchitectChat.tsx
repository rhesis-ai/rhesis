'use client';

import React, { useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  Chip,
  Switch,
  FormControlLabel,
  Tooltip,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import {
  useArchitectChat,
  ArchitectChatMessage,
  ChatAttachments,
} from '@/hooks/useArchitectChat';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ArchitectMessageBubble from './ArchitectMessageBubble';
import PlanDisplay from './PlanDisplay';
import ArchitectChatInput, {
  ArchitectChatInputHandle,
} from './ArchitectChatInput';

interface ArchitectChatProps {
  sessionId: string | null;
  sessionToken?: string;
  onSessionTitleUpdate?: (sessionId: string, title: string) => void;
  initialMessage?: string | null;
  onInitialMessageSent?: () => void;
}

interface PlanSpec {
  name?: string;
  description?: string;
  completed?: boolean;
  reuse_status?: string;
  num_tests?: number;
  test_type?: string;
  behaviors?: string[];
  behavior?: string;
  metrics?: string[];
}

function planDataToMarkdown(data: Record<string, unknown>): string {
  const lines: string[] = [];
  const project = data.project as PlanSpec | undefined;
  if (project?.name) {
    lines.push(`# ${project.name}`, '', project.description || '', '');
  }
  const behaviors = (data.behaviors || []) as PlanSpec[];
  if (behaviors.length) {
    lines.push('## Behaviors', '');
    for (const b of behaviors) {
      const box = b.completed ? '[x]' : '[ ]';
      const tag =
        b.reuse_status && b.reuse_status !== 'new'
          ? ` *(${b.reuse_status})*`
          : '';
      lines.push(`- ${box} **${b.name}**${tag}`);
      if (b.description) lines.push(`  ${b.description}`);
    }
    lines.push('');
  }
  const testSets = (data.test_sets || []) as PlanSpec[];
  if (testSets.length) {
    lines.push('## Test Sets', '');
    for (const ts of testSets) {
      const box = ts.completed ? '[x]' : '[ ]';
      lines.push(
        `- ${box} **${ts.name}** — ${ts.num_tests ?? 15} ${ts.test_type ?? 'Single-Turn'} tests`
      );
      if (ts.behaviors?.length)
        lines.push(`  Behaviors: ${ts.behaviors.join(', ')}`);
    }
    lines.push('');
  }
  const metrics = (data.metrics || []) as PlanSpec[];
  if (metrics.length) {
    lines.push('## Metrics', '');
    for (const m of metrics) {
      const box = m.completed ? '[x]' : '[ ]';
      const tag =
        m.reuse_status && m.reuse_status !== 'new'
          ? ` *(${m.reuse_status})*`
          : '';
      lines.push(`- ${box} **${m.name}**${tag}`);
    }
    lines.push('');
  }
  const mappings = data.behavior_metric_mappings as
    | PlanSpec[]
    | Record<string, string[]>
    | undefined;
  if (mappings) {
    lines.push('## Behavior-Metric Mappings', '');
    if (Array.isArray(mappings)) {
      for (const mapping of mappings) {
        const box = mapping.completed ? '[x]' : '[ ]';
        lines.push(
          `- ${box} **${mapping.behavior}** → ${(mapping.metrics || []).join(', ')}`
        );
      }
    } else {
      for (const [beh, mnames] of Object.entries(mappings)) {
        lines.push(`- [ ] **${beh}** → ${mnames.join(', ')}`);
      }
    }
    lines.push('');
  }
  return lines.join('\n');
}

const SUGGESTED_PROMPTS = [
  'I need safety and fairness tests for my LLM application',
  'Help me test for prompt injection vulnerabilities',
  'Create a comprehensive test suite for a RAG pipeline',
];

export default function ArchitectChat({
  sessionId,
  sessionToken,
  onSessionTitleUpdate: _onSessionTitleUpdate,
  initialMessage,
  onInitialMessageSent,
}: ArchitectChatProps) {
  const { data: authSession } = useSession();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<ArchitectChatInputHandle>(null);

  const {
    messages,
    isLoading,
    error,
    isConnected,
    streamingState,
    currentMode,
    currentPlan,
    isAwaitingTask,
    autoApproveAll,
    setAutoApproveAll,
    setCurrentMode,
    setCurrentPlan,
    sendMessage,
    setMessages,
  } = useArchitectChat({ sessionId, initialUserMessage: initialMessage });

  // Track sessions that were created with an initial message so we never
  // run loadMessages for them (the async fetch would wipe the messages
  // that sendMessage already added).
  const skipLoadRef = useRef<Set<string>>(new Set());

  if (sessionId && initialMessage) {
    skipLoadRef.current.add(sessionId);
  }

  // Load existing messages when session changes
  useEffect(() => {
    if (!sessionId || !sessionToken) return;
    if (skipLoadRef.current.has(sessionId)) return;

    const loadMessages = async () => {
      try {
        const client = new ApiClientFactory(sessionToken).getArchitectClient();
        const session = await client.getSession(sessionId);

        // Restore auto-approve toggle from persisted agent state
        const guardState = (session.agent_state as Record<string, unknown>)
          ?.guard_state as Record<string, unknown> | undefined;
        if (guardState?.auto_approve_all === true) {
          setAutoApproveAll(true);
        }

        // Restore mode and plan from session
        if (session.mode) {
          setCurrentMode(session.mode);
        }
        if (session.plan_data) {
          setCurrentPlan(planDataToMarkdown(session.plan_data));
        }

        if (session.messages?.length) {
          const loaded: ArchitectChatMessage[] = session.messages
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .map(m => {
              const attachments = m.attachments as
                | {
                    files?: Array<{
                      filename: string;
                      content_type: string;
                      data: string;
                      size: number;
                    }>;
                    mentions?: Array<{
                      type: string;
                      id: string;
                      display: string;
                    }>;
                  }
                | undefined;
              return {
                id: m.id,
                role: m.role as 'user' | 'assistant',
                content: m.content || '',
                timestamp: new Date(m.created_at || Date.now()),
                files: attachments?.files,
                mentions: attachments?.mentions,
              };
            });
          setMessages(loaded);
        } else {
          setMessages([]);
        }
      } catch (err) {
        console.error('Failed to load messages:', err);
      }
    };

    loadMessages();
  }, [
    sessionId,
    sessionToken,
    setMessages,
    setAutoApproveAll,
    setCurrentMode,
    setCurrentPlan,
  ]);

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
  }, [
    initialMessage,
    isConnected,
    sessionId,
    sendMessage,
    onInitialMessageSent,
  ]);

  const handleSend = useCallback(
    (message: string, attachments?: ChatAttachments) => {
      sendMessage(message, attachments);
    },
    [sendMessage]
  );

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
        borderRadius: theme => theme.shape.sharp,
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {!isConnected && (
            <Typography variant="caption" color="warning.main">
              Reconnecting...
            </Typography>
          )}
          <Tooltip title="Skip per-action confirmations — the agent will create entities without asking first">
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={autoApproveAll}
                  onChange={e => setAutoApproveAll(e.target.checked)}
                />
              }
              label={
                <Typography variant="caption" color="text.secondary">
                  Auto-approve
                </Typography>
              }
              sx={{ mr: 0 }}
            />
          </Tooltip>
        </Box>
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
            {messages.map((message, index) => {
              const hasContent =
                message.content.trim().length > 0 || message.isStreaming;

              if (
                message.role === 'assistant' &&
                !hasContent &&
                !message.isStreaming
              ) {
                return null;
              }

              const lastMsg = messages[messages.length - 1];
              const pendingConfirmation =
                !isLoading &&
                lastMsg?.role === 'assistant' &&
                !!lastMsg.needsConfirmation &&
                !autoApproveAll;

              let isLastContentAssistant = false;
              if (message.role === 'assistant' && !isLoading) {
                for (let i = messages.length - 1; i >= 0; i--) {
                  const m = messages[i];
                  if (
                    m.role === 'assistant' &&
                    (m.content.trim().length > 0 || m.isStreaming)
                  ) {
                    isLastContentAssistant = i === index;
                    break;
                  }
                }
              }

              const showActions = isLastContentAssistant && pendingConfirmation;

              const showWaitingSpinner =
                isLastContentAssistant && !showActions && isAwaitingTask;

              return (
                <ArchitectMessageBubble
                  key={message.id}
                  message={message}
                  userName={authSession?.user?.name || undefined}
                  userPicture={authSession?.user?.picture || undefined}
                  showActions={showActions}
                  showWaitingSpinner={showWaitingSpinner}
                  streamingState={
                    message.isStreaming ? streamingState : undefined
                  }
                  onAccept={() => sendMessage('Yes, go ahead.')}
                  onReject={() => chatInputRef.current?.focus()}
                />
              );
            })}

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

      {/* Input area -- key by sessionId to remount and auto-focus on session switch */}
      <ArchitectChatInput
        ref={chatInputRef}
        key={sessionId}
        onSend={handleSend}
        disabled={isLoading}
        isLoading={isLoading}
        isConnected={isConnected}
        sessionToken={sessionToken}
      />
    </Paper>
  );
}
