/**
 * WebSocket utilities for real-time communication.
 *
 * This module provides:
 * - WebSocketClient: Low-level WebSocket client with reconnection and heartbeat
 * - Types and interfaces for WebSocket messages
 */

export { WebSocketClient } from './client';
export {
  EventType,
  type WebSocketMessage,
  type WebSocketClientOptions,
  type WebSocketState,
  type EventHandler,
  type ConnectedPayload,
  type ErrorPayload,
  type SubscriptionPayload,
} from './types';
