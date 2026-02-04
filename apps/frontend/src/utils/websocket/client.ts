/**
 * WebSocket client for real-time communication with the backend.
 *
 * Features:
 * - Auto-reconnection with exponential backoff
 * - Heartbeat/ping-pong for connection health
 * - Event emitter pattern for message handling
 * - Token-based authentication via query parameter
 */

import {
  EventType,
  WebSocketMessage,
  WebSocketClientOptions,
  WebSocketState,
  EventHandler,
  ConnectedPayload,
} from './types';

/**
 * Default configuration values.
 */
const DEFAULTS = {
  reconnectInterval: 1000,
  maxReconnectAttempts: 5,
  heartbeatInterval: 30000,
} as const;

/**
 * WebSocket client class for managing connections to the backend.
 *
 * @example
 * ```typescript
 * const client = new WebSocketClient({
 *   url: 'wss://api.example.com/ws',
 *   token: 'jwt-token-here',
 * });
 *
 * // Subscribe to events
 * const unsubscribe = client.subscribe(EventType.MESSAGE, (msg) => {
 *   console.log('Received:', msg);
 * });
 *
 * // Connect
 * client.connect();
 *
 * // Send a message
 * client.send({ type: EventType.PING });
 *
 * // Subscribe to a channel
 * client.subscribeToChannel('test_run:123');
 *
 * // Cleanup
 * unsubscribe();
 * client.disconnect();
 * ```
 */
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private options: Required<WebSocketClientOptions>;
  private state: WebSocketState = {
    isConnected: false,
    reconnectAttempts: 0,
  };

  /** Event handlers mapped by event type */
  private eventHandlers: Map<string, Set<EventHandler>> = new Map();

  /** Timer for heartbeat pings */
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  /** Timer for reconnection */
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  /** Flag to track intentional disconnects */
  private intentionalDisconnect = false;

  /**
   * Create a new WebSocket client.
   *
   * @param options - Client configuration options
   */
  constructor(options: WebSocketClientOptions) {
    this.options = {
      ...options,
      reconnectInterval:
        options.reconnectInterval ?? DEFAULTS.reconnectInterval,
      maxReconnectAttempts:
        options.maxReconnectAttempts ?? DEFAULTS.maxReconnectAttempts,
      heartbeatInterval:
        options.heartbeatInterval ?? DEFAULTS.heartbeatInterval,
      onConnectionChange: options.onConnectionChange ?? (() => {}),
    };
  }

  /**
   * Connect to the WebSocket server.
   *
   * Authentication is performed via query parameter.
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    this.intentionalDisconnect = false;

    // Build URL with token
    const url = `${this.options.url}?token=${encodeURIComponent(this.options.token)}`;

    try {
      this.ws = new WebSocket(url);
      this.setupEventListeners();
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.handleClose();
    }
  }

  /**
   * Disconnect from the WebSocket server.
   *
   * This will prevent automatic reconnection.
   */
  disconnect(): void {
    this.intentionalDisconnect = true;
    this.stopHeartbeat();
    this.clearReconnectTimer();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }

    this.updateConnectionState(false);
  }

  /**
   * Send a message to the server.
   *
   * @param message - The message to send
   * @returns True if the message was sent, false otherwise
   */
  send(message: WebSocketMessage): boolean {
    if (!this.isConnected) {
      console.warn('Cannot send message: WebSocket not connected');
      return false;
    }

    try {
      this.ws?.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  /**
   * Subscribe to a specific event type.
   *
   * @param eventType - The event type to subscribe to
   * @param handler - The handler function to call when the event is received
   * @returns An unsubscribe function
   */
  subscribe(eventType: EventType | string, handler: EventHandler): () => void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      this.eventHandlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * Subscribe to a backend channel.
   *
   * This sends a SUBSCRIBE message to the server which will
   * start forwarding messages on that channel to this client.
   *
   * @param channel - The channel name to subscribe to
   */
  subscribeToChannel(channel: string): void {
    this.send({
      type: EventType.SUBSCRIBE,
      payload: { channel },
    });
  }

  /**
   * Unsubscribe from a backend channel.
   *
   * @param channel - The channel name to unsubscribe from
   */
  unsubscribeFromChannel(channel: string): void {
    this.send({
      type: EventType.UNSUBSCRIBE,
      payload: { channel },
    });
  }

  /**
   * Check if the WebSocket is connected.
   */
  get isConnected(): boolean {
    return this.state.isConnected && this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get the current connection state.
   */
  get connectionState(): WebSocketState {
    return { ...this.state };
  }

  /**
   * Get the connection ID assigned by the server.
   */
  get connectionId(): string | undefined {
    return this.state.connectionId;
  }

  // ==================== Private Methods ====================

  /**
   * Set up WebSocket event listeners.
   */
  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.state.reconnectAttempts = 0;
      this.updateConnectionState(true);
      this.startHeartbeat();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onclose = (event: CloseEvent) => {
      console.log(
        `WebSocket closed: code=${event.code}, reason=${event.reason}`
      );
      this.handleClose();
    };

    this.ws.onerror = (error: Event) => {
      console.error('WebSocket error:', error);
      this.state.lastError = 'WebSocket error occurred';
    };
  }

  /**
   * Handle an incoming message.
   */
  private handleMessage(message: WebSocketMessage): void {
    // Handle connection confirmation
    if (message.type === EventType.CONNECTED) {
      const payload = message.payload as unknown as ConnectedPayload | undefined;
      this.state.connectionId = payload?.connection_id;
      console.log(`WebSocket connection confirmed: ${this.state.connectionId}`);
    }

    // Handle pong (heartbeat response)
    if (message.type === EventType.PONG) {
      // Connection is healthy, nothing to do
      return;
    }

    // Handle errors
    if (message.type === EventType.ERROR) {
      const errorMsg =
        (message.payload as { error?: string })?.error || 'Unknown error';
      console.error('WebSocket error from server:', errorMsg);
      this.state.lastError = errorMsg;
    }

    // Dispatch to registered handlers
    const handlers = this.eventHandlers.get(message.type);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in WebSocket event handler:', error);
        }
      });
    }

    // Also dispatch to catch-all handlers (if any registered for '*')
    const catchAllHandlers = this.eventHandlers.get('*');
    if (catchAllHandlers) {
      catchAllHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in catch-all WebSocket handler:', error);
        }
      });
    }
  }

  /**
   * Handle WebSocket close event.
   */
  private handleClose(): void {
    this.stopHeartbeat();
    this.updateConnectionState(false);
    this.state.connectionId = undefined;

    // Attempt reconnection if not intentional
    if (!this.intentionalDisconnect) {
      this.attemptReconnect();
    }
  }

  /**
   * Attempt to reconnect with exponential backoff.
   */
  private attemptReconnect(): void {
    if (this.state.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.warn(
        `WebSocket max reconnect attempts (${this.options.maxReconnectAttempts}) reached`
      );
      return;
    }

    // Calculate delay with exponential backoff
    const delay =
      this.options.reconnectInterval *
      Math.pow(2, this.state.reconnectAttempts);
    this.state.reconnectAttempts++;

    console.log(
      `WebSocket reconnecting in ${delay}ms (attempt ${this.state.reconnectAttempts}/${this.options.maxReconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Clear the reconnection timer.
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Start the heartbeat timer.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: EventType.PING });
    }, this.options.heartbeatInterval);
  }

  /**
   * Stop the heartbeat timer.
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Update the connection state and notify listeners.
   */
  private updateConnectionState(isConnected: boolean): void {
    const wasConnected = this.state.isConnected;
    this.state.isConnected = isConnected;

    if (wasConnected !== isConnected) {
      this.options.onConnectionChange(isConnected);

      // Emit internal connection events
      const eventType = isConnected
        ? EventType.CONNECTED
        : EventType.DISCONNECTED;
      const handlers = this.eventHandlers.get(eventType);
      if (handlers) {
        const message: WebSocketMessage = {
          type: eventType,
          payload: isConnected
            ? { connection_id: this.state.connectionId }
            : undefined,
        };
        handlers.forEach(handler => handler(message));
      }
    }
  }
}
