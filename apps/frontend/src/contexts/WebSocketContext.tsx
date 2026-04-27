'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react';
import { useSession } from 'next-auth/react';
import {
  WebSocketClient,
  EventType,
  WebSocketMessage,
  EventHandler,
} from '@/utils/websocket';

/**
 * Context value interface for WebSocket functionality.
 */
interface WebSocketContextValue {
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Connection ID assigned by the server */
  connectionId?: string;
  /** Send a message to the server */
  send: (message: WebSocketMessage) => boolean;
  /** Subscribe to a specific event type */
  subscribe: (
    eventType: EventType | string,
    handler: EventHandler
  ) => () => void;
  /** Subscribe to a backend channel */
  subscribeToChannel: (channel: string) => void;
  /** Unsubscribe from a backend channel */
  unsubscribeFromChannel: (channel: string) => void;
  /** Manually trigger a reconnection attempt */
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: React.ReactNode;
}

interface WebSocketUrlResponse {
  url?: string;
}

async function getWebSocketUrl(): Promise<string | null> {
  const response = await fetch('/api/websocket-url', { cache: 'no-store' });
  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as WebSocketUrlResponse;
  return typeof data.url === 'string' && data.url.length > 0 ? data.url : null;
}

/**
 * WebSocket provider component.
 *
 * This provider manages a WebSocket connection to the backend and
 * exposes it through context for use in child components.
 *
 * The connection is automatically established when a user session
 * is available and torn down on logout.
 *
 * @example
 * ```tsx
 * // In your app layout
 * <WebSocketProvider>
 *   <YourApp />
 * </WebSocketProvider>
 *
 * // In a component
 * const { isConnected, subscribe, subscribeToChannel } = useWebSocketContext();
 * ```
 */
export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const { data: session, status } = useSession();
  const [isConnected, setIsConnected] = useState(false);
  const [connectionId, setConnectionId] = useState<string | undefined>();
  const clientRef = useRef<WebSocketClient | null>(null);

  // Initialize WebSocket client when session is available
  useEffect(() => {
    // Don't connect if no session or still loading
    if (status === 'loading' || !session?.session_token) {
      return;
    }

    let cancelled = false;

    getWebSocketUrl()
      .then(wsUrl => {
        if (cancelled) {
          return;
        }

        if (!wsUrl) {
          console.warn('WebSocket URL not configured.');
          return;
        }

        // Create WebSocket client
        const client = new WebSocketClient({
          url: wsUrl,
          token: session.session_token,
          onConnectionChange: connected => {
            setIsConnected(connected);
            if (!connected) {
              setConnectionId(undefined);
            }
          },
        });

        // Subscribe to connected event to capture connection ID
        client.subscribe(EventType.CONNECTED, msg => {
          const payload = msg.payload as { connection_id?: string } | undefined;
          if (payload?.connection_id) {
            setConnectionId(payload.connection_id);
          }
        });

        // Connect
        client.connect();
        clientRef.current = client;
      })
      .catch(error => {
        console.error('Failed to load WebSocket URL:', error);
      });

    return () => {
      cancelled = true;
      clientRef.current?.disconnect();
      clientRef.current = null;
      setIsConnected(false);
      setConnectionId(undefined);
    };
  }, [session?.session_token, status]);

  /**
   * Send a message to the WebSocket server.
   */
  const send = useCallback((message: WebSocketMessage): boolean => {
    if (!clientRef.current) {
      console.warn('WebSocket client not initialized');
      return false;
    }
    return clientRef.current.send(message);
  }, []);

  /**
   * Subscribe to a specific event type.
   */
  const subscribe = useCallback(
    (eventType: EventType | string, handler: EventHandler): (() => void) => {
      if (!clientRef.current) {
        console.warn('WebSocket client not initialized');
        return () => {};
      }
      return clientRef.current.subscribe(eventType, handler);
    },
    []
  );

  /**
   * Subscribe to a backend channel.
   */
  const subscribeToChannel = useCallback((channel: string): void => {
    if (!clientRef.current) {
      console.warn('WebSocket client not initialized');
      return;
    }
    clientRef.current.subscribeToChannel(channel);
  }, []);

  /**
   * Unsubscribe from a backend channel.
   */
  const unsubscribeFromChannel = useCallback((channel: string): void => {
    if (!clientRef.current) {
      console.warn('WebSocket client not initialized');
      return;
    }
    clientRef.current.unsubscribeFromChannel(channel);
  }, []);

  /**
   * Manually trigger a reconnection attempt.
   * Resets the reconnection counter and attempts to connect.
   */
  const reconnect = useCallback((): void => {
    if (!clientRef.current) {
      console.warn('WebSocket client not initialized');
      return;
    }
    clientRef.current.reconnect();
  }, []);

  // Reconnect when page becomes visible (handles mobile/laptop sleep)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        document.visibilityState === 'visible' &&
        clientRef.current &&
        !clientRef.current.isConnected
      ) {
        clientRef.current.reconnect();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const value: WebSocketContextValue = {
    isConnected,
    connectionId,
    send,
    subscribe,
    subscribeToChannel,
    unsubscribeFromChannel,
    reconnect,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

/**
 * Hook to access the WebSocket context.
 *
 * @throws Error if used outside of WebSocketProvider
 *
 * @example
 * ```tsx
 * const { isConnected, subscribe, subscribeToChannel } = useWebSocketContext();
 *
 * useEffect(() => {
 *   const unsubscribe = subscribe(EventType.MESSAGE, (msg) => {
 *     console.log('Received:', msg);
 *   });
 *   return unsubscribe;
 * }, [subscribe]);
 * ```
 */
export function useWebSocketContext(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (context === null) {
    throw new Error(
      'useWebSocketContext must be used within a WebSocketProvider'
    );
  }
  return context;
}
