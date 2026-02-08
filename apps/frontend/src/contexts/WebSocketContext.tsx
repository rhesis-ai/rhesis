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

/**
 * Get the WebSocket URL from environment variables.
 */
function getWebSocketUrl(): string | null {
  // Try NEXT_PUBLIC_WS_URL first
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (wsUrl) {
    return wsUrl;
  }

  // Derive from API URL if WS URL not set
  const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (apiUrl) {
    // Replace http(s) with ws(s) and add /ws endpoint
    const wsProtocol = apiUrl.startsWith('https://') ? 'wss://' : 'ws://';
    const baseUrl = apiUrl.replace(/^https?:\/\//, '');
    return `${wsProtocol}${baseUrl}/ws`;
  }

  return null;
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
    if (!wsUrl) {
      console.warn(
        'WebSocket URL not configured. Set NEXT_PUBLIC_WS_URL or NEXT_PUBLIC_API_BASE_URL.'
      );
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
        console.log('Page became visible, attempting WebSocket reconnection');
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
