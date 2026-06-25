import { useState, useEffect, useCallback } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { EventType, WebSocketMessage, EventHandler } from '@/utils/websocket';

/**
 * A channel to subscribe to on mount.
 *
 * Use the object form for project-scoped resource channels (e.g.
 * `test_run:{id}`, `test_set:{id}`, `architect:{id}`) so the backend can
 * satisfy the project_isolation RLS policy when it resolves the resource for
 * authorization. Omitting `projectId` for a project-scoped resource makes the
 * backend open the auth lookup with a blank project, which the fail-closed RLS
 * policy hides — the subscription is then denied and the channel silently
 * receives no events. Org-/user-scoped and ephemeral channels (e.g.
 * `preflight:{id}`) can use the plain string form.
 */
export type ChannelSubscription =
  | string
  | { channel: string; projectId?: string | null };

/**
 * Options for the useWebSocket hook.
 */
interface UseWebSocketOptions {
  /** Channels to subscribe to on mount */
  channels?: ChannelSubscription[];
  /** Handler for all messages (regardless of type) */
  onMessage?: EventHandler;
  /** Specific event type handlers */
  eventHandlers?: {
    [key in EventType | string]?: EventHandler;
  };
}

/**
 * Return value of the useWebSocket hook.
 */
interface UseWebSocketResult {
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Connection ID assigned by the server */
  connectionId?: string;
  /** Last message received (of any type) */
  lastMessage: WebSocketMessage | null;
  /** Send a message to the server */
  send: (message: WebSocketMessage) => boolean;
  /** Subscribe to a specific event type */
  subscribe: (
    eventType: EventType | string,
    handler: EventHandler
  ) => () => void;
  /** Subscribe to a backend channel */
  subscribeToChannel: (channel: string, projectId?: string | null) => void;
  /** Unsubscribe from a backend channel */
  unsubscribeFromChannel: (channel: string) => void;
  /** Manually trigger a reconnection attempt */
  reconnect: () => void;
}

/**
 * Hook for component-level WebSocket access.
 *
 * This hook provides a convenient interface for components to:
 * - Check connection status
 * - Send messages
 * - Subscribe to channels and event types
 * - Receive messages
 *
 * @param options - Configuration options
 * @returns WebSocket functionality and state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { isConnected, send, subscribe } = useWebSocket();
 *
 * // Subscribe to channels on mount
 * const { isConnected, lastMessage } = useWebSocket({
 *   channels: ['test_run:123'],
 *   eventHandlers: {
 *     [EventType.MESSAGE]: (msg) => console.log('Message:', msg),
 *   },
 * });
 *
 * // Send a message
 * send({ type: EventType.PING });
 * ```
 */
export function useWebSocket(
  options?: UseWebSocketOptions
): UseWebSocketResult {
  const {
    isConnected,
    connectionId,
    send,
    subscribe,
    subscribeToChannel,
    unsubscribeFromChannel,
    reconnect,
  } = useWebSocketContext();

  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  // Subscribe to channels on mount
  useEffect(() => {
    if (!isConnected || !options?.channels?.length) {
      return;
    }

    // Subscribe to all specified channels
    options.channels.forEach(entry => {
      const { channel, projectId } =
        typeof entry === 'string' ? { channel: entry, projectId: undefined } : entry;
      subscribeToChannel(channel, projectId);
    });

    // Unsubscribe on unmount
    return () => {
      options.channels?.forEach(entry => {
        const channel = typeof entry === 'string' ? entry : entry.channel;
        unsubscribeFromChannel(channel);
      });
    };
  }, [
    isConnected,
    options?.channels,
    subscribeToChannel,
    unsubscribeFromChannel,
  ]);

  // Set up event handlers
  useEffect(() => {
    const unsubscribers: (() => void)[] = [];

    // Set up catch-all handler if provided
    if (options?.onMessage) {
      const unsubscribe = subscribe('*', msg => {
        setLastMessage(msg);
        options.onMessage?.(msg);
      });
      unsubscribers.push(unsubscribe);
    }

    // Set up specific event handlers
    if (options?.eventHandlers) {
      Object.entries(options.eventHandlers).forEach(([eventType, handler]) => {
        if (handler) {
          const unsubscribe = subscribe(eventType, msg => {
            setLastMessage(msg);
            handler(msg);
          });
          unsubscribers.push(unsubscribe);
        }
      });
    }

    // If no handlers provided, just track last message
    if (!options?.onMessage && !options?.eventHandlers) {
      const unsubscribe = subscribe('*', setLastMessage);
      unsubscribers.push(unsubscribe);
    }

    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [subscribe, options]);

  // Memoized send function that wraps the context's send
  const sendMessage = useCallback(
    (message: WebSocketMessage): boolean => {
      return send(message);
    },
    [send]
  );

  return {
    isConnected,
    connectionId,
    lastMessage,
    send: sendMessage,
    subscribe,
    subscribeToChannel,
    unsubscribeFromChannel,
    reconnect,
  };
}
