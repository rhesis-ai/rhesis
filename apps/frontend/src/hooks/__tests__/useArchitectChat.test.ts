import { renderHook, act } from '@testing-library/react';
import { useArchitectChat } from '../useArchitectChat';
import { EventType } from '@/utils/websocket';

// Mock useWebSocket hook
const mockSend = jest.fn();
const mockSubscribe = jest.fn();
const mockSubscribeToChannel = jest.fn();
const mockUseWebSocket = jest.fn();

jest.mock('../useWebSocket', () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}));

describe('useArchitectChat', () => {
  let subscriptionHandlers: Record<string, (msg: unknown) => void>;

  beforeEach(() => {
    jest.clearAllMocks();
    subscriptionHandlers = {};

    mockSend.mockReturnValue(true);
    mockSubscribe.mockImplementation(
      (eventType: string, handler: (msg: unknown) => void) => {
        subscriptionHandlers[eventType] = handler;
        return jest.fn();
      }
    );
    mockUseWebSocket.mockReturnValue({
      isConnected: true,
      send: mockSend,
      subscribe: mockSubscribe,
      subscribeToChannel: mockSubscribeToChannel,
    });
  });

  it('returns initial state', () => {
    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.isConnected).toBe(true);
    expect(result.current.currentMode).toBe('discovery');
    expect(result.current.currentPlan).toBeNull();
  });

  it('reports disconnected state from WebSocket', () => {
    mockUseWebSocket.mockReturnValue({
      isConnected: false,
      send: mockSend,
      subscribe: mockSubscribe,
      subscribeToChannel: mockSubscribeToChannel,
    });

    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    expect(result.current.isConnected).toBe(false);
  });

  it('subscribes to architect channel when session and connection are ready', () => {
    renderHook(() => useArchitectChat({ sessionId: 'sess-1' }));

    expect(mockSubscribeToChannel).toHaveBeenCalledWith('architect:sess-1');
  });

  it('does not subscribe to channel when sessionId is null', () => {
    renderHook(() => useArchitectChat({ sessionId: null }));

    expect(mockSubscribeToChannel).not.toHaveBeenCalled();
  });

  it('does not subscribe to channel when not connected', () => {
    mockUseWebSocket.mockReturnValue({
      isConnected: false,
      send: mockSend,
      subscribe: mockSubscribe,
      subscribeToChannel: mockSubscribeToChannel,
    });

    renderHook(() => useArchitectChat({ sessionId: 'sess-1' }));

    expect(mockSubscribeToChannel).not.toHaveBeenCalled();
  });

  it('subscribes to all architect event types', () => {
    renderHook(() => useArchitectChat({ sessionId: 'sess-1' }));

    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_RESPONSE,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_THINKING,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_TOOL_START,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_TOOL_END,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_PLAN_UPDATE,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_MODE_CHANGE,
      expect.any(Function)
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_ERROR,
      expect.any(Function)
    );
  });

  it('sends a message and adds user message to state', () => {
    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
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
      useArchitectChat({ sessionId: 'sess-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(mockSend).toHaveBeenCalledWith(
      expect.objectContaining({
        type: EventType.ARCHITECT_MESSAGE,
        correlation_id: expect.any(String),
        payload: expect.objectContaining({
          session_id: 'sess-1',
          message: 'Hello',
        }),
      })
    );
  });

  it('does not send when sessionId is null', () => {
    const { result } = renderHook(() => useArchitectChat({ sessionId: null }));

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(mockSend).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
  });

  it('does not send when not connected', () => {
    mockUseWebSocket.mockReturnValue({
      isConnected: false,
      send: mockSend,
      subscribe: mockSubscribe,
      subscribeToChannel: mockSubscribeToChannel,
    });

    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(mockSend).not.toHaveBeenCalled();
  });

  it('does not send empty or whitespace-only messages', () => {
    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
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
      useArchitectChat({ sessionId: 'sess-1' })
    );

    act(() => {
      result.current.sendMessage('First');
    });
    expect(result.current.isLoading).toBe(true);

    act(() => {
      result.current.sendMessage('Second');
    });

    expect(result.current.messages).toHaveLength(1);
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('sets error when send fails', () => {
    mockSend.mockReturnValue(false);

    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    expect(result.current.error).toBe('Failed to send message');
    expect(result.current.isLoading).toBe(false);
  });

  it('trims whitespace from messages before sending', () => {
    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    act(() => {
      result.current.sendMessage('  Hello  ');
    });

    expect(result.current.messages[0].content).toBe('Hello');
    expect(mockSend.mock.calls[0][0].payload.message).toBe('Hello');
  });

  describe('ARCHITECT_RESPONSE', () => {
    it('adds assistant message and clears loading state', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        result.current.sendMessage('Hello');
      });

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Hi there!',
          },
        });
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].role).toBe('assistant');
      expect(result.current.messages[1].content).toBe('Hi there!');
      expect(result.current.isLoading).toBe(false);
    });

    it('sets needsConfirmation from payload', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Shall I create this metric?',
            needs_confirmation: true,
          },
        });
      });

      expect(result.current.messages[0].needsConfirmation).toBe(true);
    });

    it('defaults needsConfirmation to false when not present', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Here are your endpoints.',
          },
        });
      });

      expect(result.current.messages[0].needsConfirmation).toBe(false);
    });

    it('updates currentMode from response', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Plan ready.',
            mode: 'planning',
          },
        });
      });

      expect(result.current.currentMode).toBe('planning');
    });

    it('updates currentPlan from response', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Here is the plan.',
            plan: '## Test Plan\n- Safety tests',
          },
        });
      });

      expect(result.current.currentPlan).toBe('## Test Plan\n- Safety tests');
    });

    it('ignores responses for a different session', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-other',
            content: 'Should be ignored',
          },
        });
      });

      expect(result.current.messages).toEqual([]);
    });
  });

  describe('ARCHITECT_THINKING', () => {
    it('sets thinking state with iteration', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 2 },
        });
      });

      expect(result.current.streamingState.isThinking).toBe(true);
      expect(result.current.streamingState.currentIteration).toBe(2);
    });
  });

  describe('ARCHITECT_TOOL_START / ARCHITECT_TOOL_END', () => {
    it('tracks active tools', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: {
            tool: 'list_endpoints',
            description: 'Listing endpoints',
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(1);
      expect(result.current.streamingState.activeTools[0].tool).toBe(
        'list_endpoints'
      );
      expect(result.current.streamingState.activeTools[0].description).toBe(
        'Listing endpoints'
      );
    });

    it('moves tool from active to completed on tool end', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: { tool: 'list_endpoints', description: 'Listing' },
        });
      });

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_END]({
          type: EventType.ARCHITECT_TOOL_END,
          payload: {
            tool: 'list_endpoints',
            description: 'Listing',
            success: true,
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.completedTools).toHaveLength(1);
      expect(result.current.streamingState.completedTools[0].success).toBe(
        true
      );
    });

    it('ignores tool start with no tool name', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: {},
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
    });
  });

  describe('ARCHITECT_PLAN_UPDATE', () => {
    it('updates the current plan', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_PLAN_UPDATE]({
          type: EventType.ARCHITECT_PLAN_UPDATE,
          payload: { plan: '## Updated Plan' },
        });
      });

      expect(result.current.currentPlan).toBe('## Updated Plan');
    });
  });

  describe('ARCHITECT_MODE_CHANGE', () => {
    it('updates the current mode', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_MODE_CHANGE]({
          type: EventType.ARCHITECT_MODE_CHANGE,
          payload: { old_mode: 'discovery', new_mode: 'creating' },
        });
      });

      expect(result.current.currentMode).toBe('creating');
    });
  });

  describe('ARCHITECT_ERROR', () => {
    it('adds error message and clears loading state', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        result.current.sendMessage('Hello');
      });

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_ERROR]({
          type: EventType.ARCHITECT_ERROR,
          payload: {
            session_id: 'sess-1',
            error: 'Something went wrong',
          },
        });
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBe('Something went wrong');
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].role).toBe('assistant');
      expect(result.current.messages[1].content).toBe(
        'Error: Something went wrong'
      );
      expect(result.current.messages[1].isError).toBe(true);
    });

    it('ignores errors for a different session', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_ERROR]({
          type: EventType.ARCHITECT_ERROR,
          payload: {
            session_id: 'sess-other',
            error: 'Should be ignored',
          },
        });
      });

      expect(result.current.error).toBeNull();
      expect(result.current.messages).toEqual([]);
    });

    it('uses default error message when none provided', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_ERROR]({
          type: EventType.ARCHITECT_ERROR,
          payload: { session_id: 'sess-1' },
        });
      });

      expect(result.current.error).toBe('An error occurred');
    });
  });

  describe('setMessages', () => {
    it('allows external message state updates', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        result.current.setMessages([
          {
            id: 'loaded-1',
            role: 'user',
            content: 'Previously loaded',
            timestamp: new Date(),
          },
        ]);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].content).toBe('Previously loaded');
    });
  });
});
