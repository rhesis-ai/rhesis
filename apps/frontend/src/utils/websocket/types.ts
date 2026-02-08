/**
 * WebSocket types for the frontend.
 *
 * These types match the backend schemas defined in
 * apps/backend/src/rhesis/backend/app/schemas/websocket.py
 */

/**
 * WebSocket event types.
 *
 * Connection lifecycle events handle the WebSocket connection state.
 * Subscription events manage channel subscriptions.
 * Generic events are extensible for use-case specific implementations.
 */
export enum EventType {
  // Connection lifecycle
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  PING = 'ping',
  PONG = 'pong',

  // Subscriptions
  SUBSCRIBE = 'subscribe',
  UNSUBSCRIBE = 'unsubscribe',
  SUBSCRIBED = 'subscribed',
  UNSUBSCRIBED = 'unsubscribed',

  // Generic events (use-case specific events added as needed)
  NOTIFICATION = 'notification',
  MESSAGE = 'message',

  // Chat events (for playground)
  CHAT_MESSAGE = 'chat.message',
  CHAT_RESPONSE = 'chat.response',
  CHAT_ERROR = 'chat.error',
}

/**
 * WebSocket message schema.
 *
 * All messages sent over WebSocket connections follow this schema.
 */
export interface WebSocketMessage {
  /** Event type for message routing */
  type: EventType | string;
  /** Optional channel name for subscriptions */
  channel?: string;
  /** Optional arbitrary data payload */
  payload?: Record<string, unknown>;
  /** Optional ID to correlate requests with responses */
  correlation_id?: string;
}

/**
 * Event handler function type.
 */
export type EventHandler = (message: WebSocketMessage) => void;

/**
 * WebSocket client configuration options.
 */
export interface WebSocketClientOptions {
  /** WebSocket server URL (without protocol, e.g., "api.example.com/ws") */
  url: string;
  /** Authentication token (JWT or API token) */
  token: string;
  /** Base interval for reconnection attempts in ms (default: 1000) */
  reconnectInterval?: number;
  /** Maximum number of reconnection attempts (default: 10) */
  maxReconnectAttempts?: number;
  /** Maximum delay between reconnection attempts in ms (default: 30000) */
  maxReconnectDelay?: number;
  /** Interval between heartbeat pings in ms (default: 30000) */
  heartbeatInterval?: number;
  /** Callback when connection state changes */
  onConnectionChange?: (isConnected: boolean) => void;
}

/**
 * WebSocket connection state.
 */
export interface WebSocketState {
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Number of reconnection attempts so far */
  reconnectAttempts: number;
  /** Connection ID assigned by the server */
  connectionId?: string;
  /** Last error that occurred */
  lastError?: string;
}

/**
 * Connected event payload from the server.
 */
export interface ConnectedPayload {
  connection_id: string;
  user_id: string;
  org_id: string;
}

/**
 * Error event payload from the server.
 */
export interface ErrorPayload {
  error: string;
}

/**
 * Subscription confirmation payload.
 */
export interface SubscriptionPayload {
  channel: string;
}

/**
 * Chat message payload (sent to server).
 */
export interface ChatMessagePayload {
  endpoint_id: string;
  message: string;
  /** Session ID for multi-turn conversations (canonical name) */
  session_id?: string;
}

/**
 * Chat response payload (received from server).
 */
export interface ChatResponsePayload {
  output: string;
  trace_id?: string;
  endpoint_id: string;
  /** Session ID for multi-turn conversations (canonical name) */
  session_id?: string;
}

/**
 * Chat error payload (received from server).
 */
export interface ChatErrorPayload {
  error: string;
  error_type: string;
}
