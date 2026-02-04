import { useState, useCallback, useEffect, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import {
  EventType,
  WebSocketMessage,
  ChatResponsePayload,
  ChatErrorPayload,
} from '@/utils/websocket';

/**
 * Chat message interface for the playground.
 */
export interface ChatMessage {
  /** Unique message ID */
  id: string;
  /** Message role: user or assistant */
  role: 'user' | 'assistant';
  /** Message content (may contain markdown) */
  content: string;
  /** Trace ID for assistant messages (for viewing trace details) */
  traceId?: string;
  /** Timestamp when the message was created */
  timestamp: Date;
  /** Whether the message is an error */
  isError?: boolean;
}

/**
 * Options for the usePlaygroundChat hook.
 */
interface UsePlaygroundChatOptions {
  /** The endpoint ID to chat with */
  endpointId: string | null;
}

/**
 * Return value of the usePlaygroundChat hook.
 */
interface UsePlaygroundChatResult {
  /** Array of chat messages */
  messages: ChatMessage[];
  /** Whether a response is being awaited */
  isLoading: boolean;
  /** Current error message, if any */
  error: string | null;
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Current session ID for multi-turn conversations (if any) */
  sessionId: string | null;
  /** Send a message to the endpoint */
  sendMessage: (message: string) => void;
  /** Clear all messages and reset conversation */
  clearMessages: () => void;
}

/**
 * Generate a unique message ID.
 */
function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a correlation ID for request/response matching.
 */
function generateCorrelationId(): string {
  return `corr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Hook for managing playground chat state via WebSocket.
 *
 * This hook handles:
 * - Sending messages to endpoints via WebSocket
 * - Receiving and storing responses
 * - Loading and error states
 * - Correlation ID matching for request/response pairs
 *
 * @param options - Configuration options
 * @returns Chat state and functions
 *
 * @example
 * ```tsx
 * const { messages, isLoading, sendMessage, clearMessages } = usePlaygroundChat({
 *   endpointId: 'endpoint-uuid',
 * });
 *
 * // Send a message
 * sendMessage('Hello, how are you?');
 *
 * // Render messages
 * messages.map(msg => <MessageBubble key={msg.id} message={msg} />);
 * ```
 */
export function usePlaygroundChat(
  options: UsePlaygroundChatOptions
): UsePlaygroundChatResult {
  const { endpointId } = options;
  const { isConnected, send, subscribe } = useWebSocket();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Track pending correlation IDs for request/response matching
  const pendingCorrelationRef = useRef<string | null>(null);

  // Subscribe to chat response events
  useEffect(() => {
    const unsubscribeResponse = subscribe(
      EventType.CHAT_RESPONSE,
      (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ChatResponsePayload;
        const correlationId = msg.correlation_id;

        // Only process if this is the response we're waiting for
        if (
          correlationId &&
          correlationId === pendingCorrelationRef.current
        ) {
          pendingCorrelationRef.current = null;
          setIsLoading(false);
          setError(null);

          // Update session ID if provided in response
          if (payload?.session_id) {
            setSessionId(payload.session_id);
          }

          // Add assistant message
          const assistantMessage: ChatMessage = {
            id: generateMessageId(),
            role: 'assistant',
            content: payload?.output || '',
            traceId: payload?.trace_id,
            timestamp: new Date(),
          };

          setMessages(prev => [...prev, assistantMessage]);
        }
      }
    );

    const unsubscribeError = subscribe(
      EventType.CHAT_ERROR,
      (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ChatErrorPayload;
        const correlationId = msg.correlation_id;

        // Only process if this is the response we're waiting for
        if (
          correlationId &&
          correlationId === pendingCorrelationRef.current
        ) {
          pendingCorrelationRef.current = null;
          setIsLoading(false);

          const errorMessage = payload?.error || 'An error occurred';
          setError(errorMessage);

          // Add error message as assistant response
          const errorChatMessage: ChatMessage = {
            id: generateMessageId(),
            role: 'assistant',
            content: `Error: ${errorMessage}`,
            timestamp: new Date(),
            isError: true,
          };

          setMessages(prev => [...prev, errorChatMessage]);
        }
      }
    );

    return () => {
      unsubscribeResponse();
      unsubscribeError();
    };
  }, [subscribe]);

  /**
   * Send a message to the endpoint.
   */
  const sendMessage = useCallback(
    (message: string) => {
      if (!endpointId) {
        setError('No endpoint selected');
        return;
      }

      if (!isConnected) {
        setError('WebSocket not connected');
        return;
      }

      if (isLoading) {
        return; // Don't send while waiting for response
      }

      const trimmedMessage = message.trim();
      if (!trimmedMessage) {
        return;
      }

      // Clear any previous error
      setError(null);

      // Generate correlation ID for this request
      const correlationId = generateCorrelationId();
      pendingCorrelationRef.current = correlationId;

      // Add user message immediately
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        role: 'user',
        content: trimmedMessage,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, userMessage]);

      // Set loading state
      setIsLoading(true);

      // Send message via WebSocket (include session_id if we have one)
      const sent = send({
        type: EventType.CHAT_MESSAGE,
        correlation_id: correlationId,
        payload: {
          endpoint_id: endpointId,
          message: trimmedMessage,
          ...(sessionId && { session_id: sessionId }),
        },
      });

      if (!sent) {
        setIsLoading(false);
        setError('Failed to send message');
        pendingCorrelationRef.current = null;
      }
    },
    [endpointId, isConnected, isLoading, send, sessionId]
  );

  /**
   * Clear all messages and reset session.
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    setIsLoading(false);
    setSessionId(null);
    pendingCorrelationRef.current = null;
  }, []);

  // Reset session when endpoint changes
  useEffect(() => {
    setSessionId(null);
  }, [endpointId]);

  return {
    messages,
    isLoading,
    error,
    isConnected,
    sessionId,
    sendMessage,
    clearMessages,
  };
}
