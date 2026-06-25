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

  // Architect events (for architect chat)
  ARCHITECT_MESSAGE = 'architect.message',
  ARCHITECT_RESPONSE = 'architect.response',
  ARCHITECT_THINKING = 'architect.thinking',
  ARCHITECT_TOOL_START = 'architect.tool_start',
  ARCHITECT_TOOL_END = 'architect.tool_end',
  ARCHITECT_PLAN_UPDATE = 'architect.plan_update',
  ARCHITECT_MODE_CHANGE = 'architect.mode_change',
  ARCHITECT_ERROR = 'architect.error',
  ARCHITECT_STREAM_START = 'architect.stream_start',
  ARCHITECT_TEXT_CHUNK = 'architect.text_chunk',
  ARCHITECT_STREAM_END = 'architect.stream_end',
  // Live progress emitted by background workers (e.g. exploration) for
  // tasks the architect is awaiting. Carries a session_id, task_id, a
  // short label, and a status. The frontend attaches each event to the
  // awaiting bubble so the user sees per-step progress instead of a
  // bare "Working…".
  ARCHITECT_TASK_PROGRESS = 'architect.task_progress',

  // Preflight check events
  PREFLIGHT_CHECK_UPDATE = 'preflight.check_update',
  PREFLIGHT_COMPLETE = 'preflight.complete',
}

/**
 * Architect message payload (sent to server).
 */
export interface ArchitectMessagePayload {
  session_id: string;
  message: string;
  attachments?: Record<string, unknown>;
  /** When true, skip per-action confirmations for this session. */
  auto_approve?: boolean;
}

/**
 * Architect response payload (received from server).
 */
export interface ArchitectResponsePayload {
  session_id: string;
  content: string;
  mode?: string;
  plan?: string;
  needs_confirmation?: boolean;
  /** Server-side auto-approve state (echoed back for UI sync). */
  auto_approve_all?: boolean;
  /** True when the agent has dispatched a background task and is waiting for it to finish. */
  awaiting_task?: boolean;
}

/**
 * Architect thinking payload (received from server).
 */
export interface ArchitectThinkingPayload {
  status: string;
  iteration?: number;
  session_id?: string;
}

/**
 * Architect tool event payload (received from server).
 */
export interface ArchitectToolPayload {
  tool: string;
  description?: string;
  args?: Record<string, unknown>;
  reasoning?: string;
  success?: boolean;
  preview?: string;
  duration_ms?: number;
}

/**
 * Architect plan update payload (received from server).
 */
export interface ArchitectPlanUpdatePayload {
  plan: string;
}

/**
 * Architect mode change payload (received from server).
 */
export interface ArchitectModeChangePayload {
  old_mode: string;
  new_mode: string;
}

/**
 * Architect stream start payload (received from server).
 */
export interface ArchitectStreamStartPayload {
  needs_confirmation?: boolean;
}

/**
 * Architect text chunk payload (received from server).
 */
export interface ArchitectTextChunkPayload {
  chunk: string;
}

/**
 * Architect stream end payload (received from server).
 */
export interface ArchitectStreamEndPayload {
  content: string;
  error?: string | null;
}

/**
 * Architect task-progress payload (received from server).
 *
 * Emitted by background workers as they make progress on a task the
 * architect is currently awaiting. The frontend attaches each event
 * to the awaiting message bubble so the user sees what's happening.
 */
export interface ArchitectTaskProgressPayload {
  session_id: string;
  /** Celery task id of the awaited task. */
  task_id: string;
  /** "started" | "progress" | "completed" | "failed" */
  status: 'started' | 'progress' | 'completed' | 'failed';
  /** Short human-readable label, e.g. "Running domain probing strategy". */
  label: string;
  /** Current step number (1-based), if applicable. */
  step?: number;
  /** Total number of steps, if known. */
  total?: number;
  /** Optional milliseconds the step took (only set on completion). */
  duration_ms?: number;
}

/**
 * Architect error payload (received from server).
 */
export interface ArchitectErrorPayload {
  error: string;
  error_type?: string;
  session_id?: string;
}

/**
 * Preflight check update payload (received from server).
 */
export interface PreflightCheckUpdatePayload {
  check_id: string;
  label: string;
  status: 'running' | 'passed' | 'failed' | 'warning' | 'skipped';
  message?: string;
  detail?: string;
  correlation_id: string;
  test_set_id?: string;
  test_set_name?: string;
  composite_key?: string;
}

/**
 * Preflight complete payload (received from server).
 */
export interface PreflightCompletePayload {
  correlation_id: string;
  summary: 'passed' | 'failed' | 'warning';
  passed: number;
  failed: number;
  warnings: number;
  skipped: number;
  checks?: PreflightCheckUpdatePayload[];
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
 * File attachment for playground chat messages.
 */
export interface FileAttachment {
  filename: string;
  content_type: string;
  data: string;
}

/**
 * Chat message payload (sent to server).
 */
export interface ChatMessagePayload {
  endpoint_id: string;
  message: string;
  /** Conversation ID for multi-turn conversations (canonical name) */
  conversation_id?: string;
  /** Optional file attachments */
  files?: FileAttachment[];
}

/**
 * Chat response payload (received from server).
 */
export interface ChatResponsePayload {
  output: string;
  trace_id?: string;
  endpoint_id: string;
  /** Conversation ID for multi-turn conversations (canonical name) */
  conversation_id?: string;
  /** Output files returned by the endpoint */
  output_files?: FileAttachment[];
}

/**
 * Chat error payload (received from server).
 */
export interface ChatErrorPayload {
  error: string;
  error_type: string;
}
