import { useState, useCallback, useEffect, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import {
  EventType,
  WebSocketMessage,
  ArchitectResponsePayload,
  ArchitectThinkingPayload,
  ArchitectToolPayload,
  ArchitectPlanUpdatePayload,
  ArchitectModeChangePayload,
  ArchitectErrorPayload,
  ArchitectTextChunkPayload,
  ArchitectStreamEndPayload,
} from '@/utils/websocket';

export interface ArchitectChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'event';
  content: string;
  timestamp: Date;
  isError?: boolean;
  needsConfirmation?: boolean;
  isStreaming?: boolean;
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

export interface StreamingState {
  isThinking: boolean;
  currentIteration?: number;
  activeTools: Array<{
    tool: string;
    description?: string;
    args?: Record<string, unknown>;
    reasoning?: string;
  }>;
  completedTools: Array<{
    tool: string;
    description?: string;
    success: boolean;
    preview?: string;
    reasoning?: string;
  }>;
}

interface UseArchitectChatOptions {
  sessionId: string | null;
}

export interface ChatAttachments {
  mentions?: Array<{ type: string; id: string; display: string }>;
  files?: Array<{
    filename: string;
    content_type: string;
    data: string;
    size: number;
  }>;
}

interface UseArchitectChatResult {
  messages: ArchitectChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  streamingState: StreamingState;
  currentMode: string;
  currentPlan: string | null;
  autoApproveAll: boolean;
  setAutoApproveAll: React.Dispatch<React.SetStateAction<boolean>>;
  sendMessage: (message: string, attachments?: ChatAttachments) => void;
  setMessages: React.Dispatch<React.SetStateAction<ArchitectChatMessage[]>>;
}

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function generateCorrelationId(): string {
  return `corr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

const initialStreamingState: StreamingState = {
  isThinking: false,
  activeTools: [],
  completedTools: [],
};

export function useArchitectChat(
  options: UseArchitectChatOptions
): UseArchitectChatResult {
  const { sessionId } = options;
  const { isConnected, send, subscribe, subscribeToChannel } = useWebSocket();

  const [messages, setMessages] = useState<ArchitectChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingState, setStreamingState] = useState<StreamingState>(
    initialStreamingState
  );
  const [currentMode, setCurrentMode] = useState('discovery');
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [autoApproveAll, setAutoApproveAll] = useState(false);

  const pendingCorrelationRef = useRef<string | null>(null);
  const streamingMessageIdRef = useRef<string | null>(null);
  const autoApproveRef = useRef(autoApproveAll);
  autoApproveRef.current = autoApproveAll;

  // Subscribe to architect channel when session changes
  useEffect(() => {
    if (!sessionId || !isConnected) return;

    const channel = `architect:${sessionId}`;
    subscribeToChannel(channel);
  }, [sessionId, isConnected, subscribeToChannel]);

  // Subscribe to all architect event types
  useEffect(() => {
    const unsubs: Array<() => void> = [];

    // Helper: ensure a streaming assistant message exists, return its ID
    const ensureStreamingMessage = (): string => {
      if (streamingMessageIdRef.current) return streamingMessageIdRef.current;
      const msgId = generateId();
      streamingMessageIdRef.current = msgId;
      const msg: ArchitectChatMessage = {
        id: msgId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages(prev => [...prev, msg]);
      return msgId;
    };

    unsubs.push(
      subscribe(EventType.ARCHITECT_THINKING, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectThinkingPayload;
        ensureStreamingMessage();
        setStreamingState(prev => ({
          ...prev,
          isThinking: true,
          currentIteration: payload?.iteration ?? prev.currentIteration,
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_STREAM_START, (_msg: WebSocketMessage) => {
        // Message already created by THINKING; just ensure it exists
        ensureStreamingMessage();
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TEXT_CHUNK, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectTextChunkPayload;
        const streamId = streamingMessageIdRef.current;
        if (!streamId || !payload?.chunk) return;

        setMessages(prev =>
          prev.map(m =>
            m.id === streamId ? { ...m, content: m.content + payload.chunk } : m
          )
        );
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_STREAM_END, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectStreamEndPayload;
        const streamId = streamingMessageIdRef.current;

        if (streamId && payload) {
          setMessages(prev =>
            prev.map(m =>
              m.id === streamId
                ? {
                    ...m,
                    content: payload.error
                      ? m.content || payload.content
                      : m.content,
                    isError: !!payload.error,
                  }
                : m
            )
          );
        }
        // Don't clear streamingMessageIdRef yet — wait for ARCHITECT_RESPONSE
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_RESPONSE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectResponsePayload;
        if (payload?.session_id !== sessionId) return;

        setIsLoading(false);
        setStreamingState(initialStreamingState);
        setError(null);
        pendingCorrelationRef.current = null;

        if (payload.mode) setCurrentMode(payload.mode);
        if (payload.plan) setCurrentPlan(payload.plan);

        const streamId = streamingMessageIdRef.current;
        if (streamId) {
          // Finalize the streaming message
          setMessages(prev =>
            prev.map(m =>
              m.id === streamId
                ? {
                    ...m,
                    isStreaming: false,
                    needsConfirmation: payload.needs_confirmation ?? false,
                  }
                : m
            )
          );
          streamingMessageIdRef.current = null;
        } else {
          // Fallback: no streaming message exists (backward compatibility)
          const assistantMessage: ArchitectChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: payload.content || '',
            timestamp: new Date(),
            needsConfirmation: payload.needs_confirmation ?? false,
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TOOL_START, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectToolPayload;
        if (!payload?.tool) return;
        setStreamingState(prev => ({
          ...prev,
          activeTools: [
            ...prev.activeTools,
            {
              tool: payload.tool,
              description: payload.description,
              args: payload.args,
              reasoning: payload.reasoning,
            },
          ],
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TOOL_END, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectToolPayload;
        if (!payload?.tool) return;
        setStreamingState(prev => {
          const activeTool = prev.activeTools.find(t => t.tool === payload.tool);
          return {
            ...prev,
            activeTools: prev.activeTools.filter(t => t.tool !== payload.tool),
            completedTools: [
              ...prev.completedTools,
              {
                tool: payload.tool,
                description: payload.description,
                success: payload.success ?? true,
                preview: payload.preview,
                reasoning: activeTool?.reasoning || payload.reasoning,
              },
            ],
          };
        });
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_PLAN_UPDATE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectPlanUpdatePayload;
        if (payload?.plan) setCurrentPlan(payload.plan);
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_MODE_CHANGE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectModeChangePayload;
        if (payload?.new_mode) setCurrentMode(payload.new_mode);
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_ERROR, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectErrorPayload;
        if (payload?.session_id && payload.session_id !== sessionId) return;

        setIsLoading(false);
        setStreamingState(initialStreamingState);
        pendingCorrelationRef.current = null;

        const errorMsg = payload?.error || 'An error occurred';
        setError(errorMsg);

        setMessages(prev => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: `Error: ${errorMsg}`,
            timestamp: new Date(),
            isError: true,
          },
        ]);
      })
    );

    return () => unsubs.forEach(fn => fn());
  }, [subscribe, sessionId]);

  const sendMessage = useCallback(
    (message: string, attachments?: ChatAttachments) => {
      if (!sessionId || !isConnected || isLoading) return;

      const trimmed = message.trim();
      if (!trimmed) return;

      setError(null);

      const correlationId = generateCorrelationId();
      pendingCorrelationRef.current = correlationId;

      setMessages(prev => [
        ...prev,
        {
          id: generateId(),
          role: 'user',
          content: trimmed,
          timestamp: new Date(),
          files: attachments?.files,
          mentions: attachments?.mentions,
        },
      ]);

      setIsLoading(true);
      setStreamingState(initialStreamingState);

      const payload: Record<string, unknown> = {
        session_id: sessionId,
        message: trimmed,
      };
      if (attachments) {
        payload.attachments = attachments;
      }
      if (autoApproveRef.current) {
        payload.auto_approve = true;
      }

      const sent = send({
        type: EventType.ARCHITECT_MESSAGE,
        correlation_id: correlationId,
        payload,
      });

      if (!sent) {
        setIsLoading(false);
        setError('Failed to send message');
        pendingCorrelationRef.current = null;
      }
    },
    [sessionId, isConnected, isLoading, send]
  );

  return {
    messages,
    isLoading,
    error,
    isConnected,
    streamingState,
    currentMode,
    currentPlan,
    autoApproveAll,
    setAutoApproveAll,
    sendMessage,
    setMessages,
  };
}
