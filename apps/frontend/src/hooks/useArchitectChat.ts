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
} from '@/utils/websocket';

export interface ArchitectChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'event';
  content: string;
  timestamp: Date;
  isError?: boolean;
}

export interface StreamingState {
  isThinking: boolean;
  currentIteration?: number;
  activeTools: Array<{ tool: string; args?: Record<string, unknown> }>;
  completedTools: Array<{
    tool: string;
    success: boolean;
    preview?: string;
  }>;
}

interface UseArchitectChatOptions {
  sessionId: string | null;
}

interface UseArchitectChatResult {
  messages: ArchitectChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  streamingState: StreamingState;
  currentMode: string;
  currentPlan: string | null;
  sendMessage: (message: string) => void;
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
  const [streamingState, setStreamingState] =
    useState<StreamingState>(initialStreamingState);
  const [currentMode, setCurrentMode] = useState('discovery');
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);

  const pendingCorrelationRef = useRef<string | null>(null);

  // Subscribe to architect channel when session changes
  useEffect(() => {
    if (!sessionId || !isConnected) return;

    const channel = `architect:${sessionId}`;
    subscribeToChannel(channel);
  }, [sessionId, isConnected, subscribeToChannel]);

  // Subscribe to all architect event types
  useEffect(() => {
    const unsubs: Array<() => void> = [];

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

        const assistantMessage: ArchitectChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: payload.content || '',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMessage]);
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_THINKING, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectThinkingPayload;
        setStreamingState(prev => ({
          ...prev,
          isThinking: true,
          currentIteration: payload?.iteration ?? prev.currentIteration,
        }));
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
            { tool: payload.tool, args: payload.args },
          ],
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TOOL_END, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectToolPayload;
        if (!payload?.tool) return;
        setStreamingState(prev => ({
          ...prev,
          activeTools: prev.activeTools.filter(t => t.tool !== payload.tool),
          completedTools: [
            ...prev.completedTools,
            {
              tool: payload.tool,
              success: payload.success ?? true,
              preview: payload.preview,
            },
          ],
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_PLAN_UPDATE, (msg: WebSocketMessage) => {
        const payload =
          msg.payload as unknown as ArchitectPlanUpdatePayload;
        if (payload?.plan) setCurrentPlan(payload.plan);
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_MODE_CHANGE, (msg: WebSocketMessage) => {
        const payload =
          msg.payload as unknown as ArchitectModeChangePayload;
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
    (message: string) => {
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
        },
      ]);

      setIsLoading(true);
      setStreamingState(initialStreamingState);

      const sent = send({
        type: EventType.ARCHITECT_MESSAGE,
        correlation_id: correlationId,
        payload: {
          session_id: sessionId,
          message: trimmed,
        },
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
    sendMessage,
    setMessages,
  };
}
