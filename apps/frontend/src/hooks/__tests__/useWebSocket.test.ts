import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';
import { EventType, WebSocketMessage } from '@/utils/websocket';

// ---------------------------------------------------------------------------
// Mock the WebSocketContext — useWebSocket is a thin wrapper around it
// ---------------------------------------------------------------------------

const mockSend = jest.fn().mockReturnValue(true);
const mockSubscribe = jest.fn();
const mockSubscribeToChannel = jest.fn();
const mockUnsubscribeFromChannel = jest.fn();
const mockReconnect = jest.fn();

jest.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    isConnected: mockIsConnected(),
    connectionId: mockConnectionId(),
    send: mockSend,
    subscribe: mockSubscribe,
    subscribeToChannel: mockSubscribeToChannel,
    unsubscribeFromChannel: mockUnsubscribeFromChannel,
    reconnect: mockReconnect,
  }),
}));

// Helper state so individual tests can control connection state
let _isConnected = true;
let _connectionId: string | undefined = 'conn-abc-123';

function mockIsConnected() {
  return _isConnected;
}
function mockConnectionId() {
  return _connectionId;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useWebSocket', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    _isConnected = true;
    _connectionId = 'conn-abc-123';

    // Default subscribe implementation returns an unsubscribe fn
    mockSubscribe.mockImplementation(() => jest.fn());
  });

  describe('initial state', () => {
    it('exposes isConnected and connectionId from context', () => {
      const { result } = renderHook(() => useWebSocket());

      expect(result.current.isConnected).toBe(true);
      expect(result.current.connectionId).toBe('conn-abc-123');
    });

    it('starts with lastMessage as null', () => {
      const { result } = renderHook(() => useWebSocket());

      expect(result.current.lastMessage).toBeNull();
    });

    it('exposes send, subscribe, subscribeToChannel, unsubscribeFromChannel, reconnect', () => {
      const { result } = renderHook(() => useWebSocket());

      expect(typeof result.current.send).toBe('function');
      expect(typeof result.current.subscribe).toBe('function');
      expect(typeof result.current.subscribeToChannel).toBe('function');
      expect(typeof result.current.unsubscribeFromChannel).toBe('function');
      expect(typeof result.current.reconnect).toBe('function');
    });
  });

  describe('send', () => {
    it('delegates to context send and returns its result', () => {
      const { result } = renderHook(() => useWebSocket());

      const msg: WebSocketMessage = { type: EventType.PING };
      const sent = result.current.send(msg);

      expect(mockSend).toHaveBeenCalledWith(msg);
      expect(sent).toBe(true);
    });
  });

  describe('channel subscriptions', () => {
    it('subscribes to specified channels when connected', () => {
      renderHook(() =>
        useWebSocket({ channels: ['test_run:123', 'test_run:456'] })
      );

      expect(mockSubscribeToChannel).toHaveBeenCalledWith('test_run:123');
      expect(mockSubscribeToChannel).toHaveBeenCalledWith('test_run:456');
    });

    it('does not subscribe to channels when not connected', () => {
      _isConnected = false;

      renderHook(() => useWebSocket({ channels: ['test_run:123'] }));

      expect(mockSubscribeToChannel).not.toHaveBeenCalled();
    });

    it('unsubscribes from channels on unmount', () => {
      const { unmount } = renderHook(() =>
        useWebSocket({ channels: ['test_run:123'] })
      );

      unmount();

      expect(mockUnsubscribeFromChannel).toHaveBeenCalledWith('test_run:123');
    });
  });

  describe('event handlers', () => {
    it('sets up a catch-all handler when onMessage is provided', () => {
      const onMessage = jest.fn();

      renderHook(() => useWebSocket({ onMessage }));

      expect(mockSubscribe).toHaveBeenCalledWith('*', expect.any(Function));
    });

    it('sets up specific event-type handlers when eventHandlers is provided', () => {
      const messageHandler = jest.fn();

      renderHook(() =>
        useWebSocket({
          eventHandlers: {
            [EventType.MESSAGE]: messageHandler,
          },
        })
      );

      expect(mockSubscribe).toHaveBeenCalledWith(
        EventType.MESSAGE,
        expect.any(Function)
      );
    });

    it('sets up a catch-all handler when no options are provided', () => {
      renderHook(() => useWebSocket());

      expect(mockSubscribe).toHaveBeenCalledWith('*', expect.any(Function));
    });

    it('updates lastMessage when a message is received through the catch-all handler', () => {
      const capturedHandlers: Array<(msg: WebSocketMessage) => void> = [];
      mockSubscribe.mockImplementation(
        (_eventType: string, handler: (msg: WebSocketMessage) => void) => {
          capturedHandlers.push(handler);
          return jest.fn();
        }
      );

      const { result } = renderHook(() => useWebSocket());

      const incomingMessage: WebSocketMessage = {
        type: EventType.MESSAGE,
        payload: { text: 'hello' },
      };

      act(() => {
        capturedHandlers.forEach(h => h(incomingMessage));
      });

      expect(result.current.lastMessage).toEqual(incomingMessage);
    });

    it('cleans up subscriptions on unmount', () => {
      const mockUnsubscribe = jest.fn();
      mockSubscribe.mockReturnValue(mockUnsubscribe);

      const { unmount } = renderHook(() => useWebSocket());

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });
});
