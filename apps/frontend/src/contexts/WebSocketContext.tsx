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
import { getClientApiBaseUrl } from '@/utils/url-resolver';
import { WebSocketTokenClient } from '@/utils/api-client/websocket-token-client';

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
  subscribeToChannel: (channel: string, projectId?: string | null) => void;
  /** Unsubscribe from a backend channel */
  unsubscribeFromChannel: (channel: string) => void;
  /** Manually trigger a reconnection attempt */
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: React.ReactNode;
}

/**
 * Derive WebSocket URL from runtime API base URL (http(s) → ws(s), path /ws).
 */
function getWebSocketUrl(): string {
  const apiUrl = getClientApiBaseUrl();
  const wsProtocol = apiUrl.startsWith('https://') ? 'wss://' : 'ws://';
  const baseUrl = apiUrl.replace(/^https?:\/\//, '');
  return `${wsProtocol}${baseUrl}/ws`;
}

/**
 * Returns a `tokenProvider` function bound to the given session token.
 *
 * Each call to the provider fetches a fresh short-lived WS token from
 * `POST /ws/token`, so every connection attempt (including auto-reconnects)
 * uses a valid single-use credential instead of the long-lived session JWT.
 */
function makeWsTokenProvider(sessionToken: string): () => Promise<string> {
  return async () => {
    const client = new WebSocketTokenClient(sessionToken);
    const { token } = await client.getWebSocketToken();
    return token;
  };
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

    const wsUrl = getWebSocketUrl();

    // Create WebSocket client. The tokenProvider fetches a fresh short-lived
    // WS token before each connection attempt (including auto-reconnects),
    // keeping the long-lived session JWT out of the WebSocket URL.
    // The static token acts as a fallback if the provider call fails.
    const client = new WebSocketClient({
      url: wsUrl,
      token: session.session_token,
      tokenProvider: makeWsTokenProvider(session.session_token),
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

    // Cleanup on unmount or session change
    return () => {
      client.disconnect();
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
  const subscribeToChannel = useCallback(
    (channel: string, projectId?: string | null): void => {
      if (!clientRef.current) {
        console.warn('WebSocket client not initialized');
        return;
      }
      clientRef.current.subscribeToChannel(channel, projectId);
    },
    []
  );

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
