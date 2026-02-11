import { renderHook, act } from '@testing-library/react';
import { usePlaygroundChat } from '../usePlaygroundChat';
import { EventType } from '@/utils/websocket';

// Mock useWebSocket hook
const mockSend = jest.fn();
const mockSubscribe = jest.fn();
const mockUseWebSocket = jest.fn();

jest.mock('../useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}));

describe('usePlaygroundChat', () => {
  // Track subscriptions so we can simulate incoming messages
  let subscriptionHandlers: Record<string, (msg: unknown) => void>;

  beforeEach(() => {
    jest.clearAllMocks();
    subscriptionHandlers = {};

    // Default: connected WebSocket
    mockSend.mockReturnValue(true);
    mockSubscribe.mockImplementation(
      (eventType: string, handler: (msg: unknown) => void) => {
        subscriptionHandlers[eventType] = handler;
        return jest.fn(); // unsubscribe function
      }
    );
    mockUseWebSocket.mockReturnValue({
      isConnected: true,
      send: mockSend,
      subscribe: mockSubscribe,
    });
  });

  it('returns initial state', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.isConnected).toBe(true);
    expect(result.current.sessionId).toBeNull();
  });

  it('reports disconnected state from WebSocket', () => {
    mockUseWebSocket.mockReturnValue({
      isConnected: false,
      send: mockSend,
      subscribe: mockSubscribe,
    });

    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    expect(result.current.isConnected).toBe(false);
  });

  it('subscribes to CHAT_RESPONSE and CHAT_ERROR events', () => {
    renderHook(() => usePlaygroundChat({ endpointId: 'ep-1' }));

    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.CHAT_RESPONSE,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.CHAT_ERROR,
      expect.any(Function)
    );
  });

  it('sends a message and adds user message to state', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('Hello');
    expect(result.current.isLoading).toBe(true);
  });

  it('sends message via WebSocket with correct payload', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(mockSend).toHaveBeenCalledWith(
      expect.objectContaining({
        type: EventType.CHAT_MESSAGE,
        correlation_id: expect.any(String),
        payload: expect.objectContaining({
          endpoint_id: 'ep-1',
          message: 'Hello',
        }),
      })
    );
  });

  it('sets error when no endpoint is selected', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: null })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(result.current.error).toBe('No endpoint selected');
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('sets error when WebSocket is not connected', () => {
    mockUseWebSocket.mockReturnValue({
      isConnected: false,
      send: mockSend,
      subscribe: mockSubscribe,
    });

    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(result.current.error).toBe('WebSocket not connected');
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('does not send empty or whitespace-only messages', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('');
    });
    expect(mockSend).not.toHaveBeenCalled();

    act(() => {
      result.current.sendMessage('   ');
    });
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('does not send while loading', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    // Send first message to enter loading state
    act(() => {
      result.current.sendMessage('First');
    });
    expect(result.current.isLoading).toBe(true);

    // Try to send again while loading
    act(() => {
      result.current.sendMessage('Second');
    });

    // Should still only have the first user message
    expect(result.current.messages).toHaveLength(1);
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('sets error when send fails', () => {
    mockSend.mockReturnValue(false);

    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(result.current.error).toBe('Failed to send message');
    expect(result.current.isLoading).toBe(false);
  });

  it('handles chat response and adds assistant message', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    // Send a message to get a correlation_id
    act(() => {
      result.current.sendMessage('Hello');
    });

    // Get the correlation_id from the sent message
    const sentCall = mockSend.mock.calls[0][0];
    const correlationId = sentCall.correlation_id;

    // Simulate a chat response
    act(() => {
      subscriptionHandlers[EventType.CHAT_RESPONSE]({
        type: EventType.CHAT_RESPONSE,
        correlation_id: correlationId,
        payload: {
          output: 'Hi there!',
          trace_id: 'trace-123',
          endpoint_id: 'ep-1',
          session_id: 'sess-1',
        },
      });
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].role).toBe('assistant');
    expect(result.current.messages[1].content).toBe('Hi there!');
    expect(result.current.messages[1].traceId).toBe('trace-123');
    expect(result.current.isLoading).toBe(false);
    expect(result.current.sessionId).toBe('sess-1');
  });

  it('ignores responses with non-matching correlation ID', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    // Simulate a response with a different correlation_id
    act(() => {
      subscriptionHandlers[EventType.CHAT_RESPONSE]({
        type: EventType.CHAT_RESPONSE,
        correlation_id: 'wrong-correlation',
        payload: {
          output: 'Should be ignored',
          endpoint_id: 'ep-1',
        },
      });
    });

    // Only the user message should be present
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.isLoading).toBe(true);
  });

  it('handles chat error and adds error message', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    const sentCall = mockSend.mock.calls[0][0];
    const correlationId = sentCall.correlation_id;

    // Simulate a chat error
    act(() => {
      subscriptionHandlers[EventType.CHAT_ERROR]({
        type: EventType.CHAT_ERROR,
        correlation_id: correlationId,
        payload: {
          error: 'Endpoint timeout',
          error_type: 'timeout',
        },
      });
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[1].role).toBe('assistant');
    expect(result.current.messages[1].content).toBe('Error: Endpoint timeout');
    expect(result.current.messages[1].isError).toBe(true);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBe('Endpoint timeout');
  });

  it('clearMessages resets all state', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    // Send a message
    act(() => {
      result.current.sendMessage('Hello');
    });

    // Receive a response to populate sessionId
    const sentCall = mockSend.mock.calls[0][0];
    act(() => {
      subscriptionHandlers[EventType.CHAT_RESPONSE]({
        type: EventType.CHAT_RESPONSE,
        correlation_id: sentCall.correlation_id,
        payload: {
          output: 'Hi!',
          endpoint_id: 'ep-1',
          session_id: 'sess-1',
        },
      });
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.sessionId).toBe('sess-1');

    // Clear
    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.sessionId).toBeNull();
  });

  it('resets state when endpoint changes', () => {
    const { result, rerender } = renderHook(
      ({ endpointId }) => usePlaygroundChat({ endpointId }),
      { initialProps: { endpointId: 'ep-1' as string | null } }
    );

    // Send a message
    act(() => {
      result.current.sendMessage('Hello');
    });
    expect(result.current.messages).toHaveLength(1);

    // Change endpoint
    rerender({ endpointId: 'ep-2' });

    expect(result.current.messages).toEqual([]);
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.sessionId).toBeNull();
  });

  it('includes session_id in subsequent messages', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    // Send first message
    act(() => {
      result.current.sendMessage('Hello');
    });

    // Simulate response with session_id
    const firstCall = mockSend.mock.calls[0][0];
    act(() => {
      subscriptionHandlers[EventType.CHAT_RESPONSE]({
        type: EventType.CHAT_RESPONSE,
        correlation_id: firstCall.correlation_id,
        payload: {
          output: 'Hi!',
          endpoint_id: 'ep-1',
          session_id: 'sess-1',
        },
      });
    });

    // Send second message
    act(() => {
      result.current.sendMessage('How are you?');
    });

    // Second send call should include session_id
    expect(mockSend).toHaveBeenCalledTimes(2);
    const secondCall = mockSend.mock.calls[1][0];
    expect(secondCall.payload.session_id).toBe('sess-1');
  });

  it('trims whitespace from messages before sending', () => {
    const { result } = renderHook(() =>
      usePlaygroundChat({ endpointId: 'ep-1' })
    );

    act(() => {
      result.current.sendMessage('  Hello  ');
    });

    expect(result.current.messages[0].content).toBe('Hello');
    expect(mockSend.mock.calls[0][0].payload.message).toBe('Hello');
  });
});
