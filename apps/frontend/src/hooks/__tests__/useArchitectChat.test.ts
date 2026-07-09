import { renderHook, act } from '@testing-library/react';
import { useArchitectChat } from '../useArchitectChat';
import { EventType } from '@/utils/websocket';

// Mock useWebSocket hook
const mockSend = jest.fn();
const mockSubscribe = jest.fn();
const mockSubscribeToChannel = jest.fn();
const mockUnsubscribeFromChannel = jest.fn();
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
      unsubscribeFromChannel: mockUnsubscribeFromChannel,
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
      unsubscribeFromChannel: mockUnsubscribeFromChannel,
    });

    const { result } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    expect(result.current.isConnected).toBe(false);
  });

  it('subscribes to architect channel when session and connection are ready', () => {
    renderHook(() => useArchitectChat({ sessionId: 'sess-1' }));

    expect(mockSubscribeToChannel).toHaveBeenCalledWith(
      'architect:sess-1',
      undefined
    );
  });

  it('passes sessionProjectId when subscribing to architect channel', () => {
    renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1', sessionProjectId: 'proj-42' })
    );

    expect(mockSubscribeToChannel).toHaveBeenCalledWith(
      'architect:sess-1',
      'proj-42'
    );
  });

  it('unsubscribes from architect channel on unmount', () => {
    const { unmount } = renderHook(() =>
      useArchitectChat({ sessionId: 'sess-1' })
    );

    unmount();

    expect(mockUnsubscribeFromChannel).toHaveBeenCalledWith('architect:sess-1');
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
      unsubscribeFromChannel: mockUnsubscribeFromChannel,
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
    expect(mockSubscribe).toHaveBeenCalledWith(
      EventType.ARCHITECT_TASK_PROGRESS,
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
      unsubscribeFromChannel: mockUnsubscribeFromChannel,
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

    it('drops internal bookkeeping tools (save_plan) from the visible lists', () => {
      // ``save_plan`` is the agent's own state-persistence call, not a
      // user-facing action. The LLM frequently fails Pydantic
      // validation on the first attempt and self-corrects on the
      // second; surfacing that as "Save Plan ❌ → Save Plan ✓" was
      // confusing users into thinking something actually broke.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: { tool: 'save_plan', description: 'Saving plan' },
        });
      });
      expect(result.current.streamingState.activeTools).toHaveLength(0);

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_END]({
          type: EventType.ARCHITECT_TOOL_END,
          payload: {
            tool: 'save_plan',
            description: 'Saving plan',
            success: false,
          },
        });
      });
      // Even the failed end event must not leak into completedTools —
      // the whole point is that the user shouldn't see the noisy
      // mid-step retry at all.
      expect(result.current.streamingState.completedTools).toHaveLength(0);
    });

    it('still surfaces non-internal tools that happen alongside save_plan', () => {
      // Sanity check: the filter is narrow. Real tool calls in the
      // same step (e.g. ``list_metrics``) must continue to render.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: { tool: 'save_plan', description: 'Saving plan' },
        });
        subscriptionHandlers[EventType.ARCHITECT_TOOL_START]({
          type: EventType.ARCHITECT_TOOL_START,
          payload: { tool: 'list_metrics', description: 'Listing metrics' },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(1);
      expect(result.current.streamingState.activeTools[0].tool).toBe(
        'list_metrics'
      );
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
      expect(result.current.messages[1].content).toBe('Something went wrong');
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

  describe('long-task completion marker', () => {
    /**
     * Helper: drive the hook through a full wait cycle —
     * 1. user sends a message
     * 2. agent replies with `awaiting_task: true` (Working… spinner on)
     * 3. agent sends a follow-up reply with `awaiting_task: false`
     *    (long task finished)
     *
     * Returns the message id of the bubble that owned the spinner.
     */
    const startWaitingThenComplete = (
      result: ReturnType<typeof renderHook>['result']
    ): string => {
      const r = result as unknown as {
        current: ReturnType<typeof useArchitectChat>;
      };
      // 1. user message
      act(() => {
        r.current.sendMessage('Generate the test set');
      });
      // 2a. THINKING creates the streaming bubble for the assistant turn
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 1 },
        });
      });
      const streamingMsg = r.current.messages.find(m => m.isStreaming);
      if (!streamingMsg) {
        throw new Error('expected a streaming assistant message');
      }
      // 2b. RESPONSE finalises that bubble and flips on awaiting_task
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Kicking off generation…',
            awaiting_task: true,
          },
        });
      });
      return streamingMsg.id;
    };

    /**
     * Helper: ARCHITECT_THINKING + RESPONSE with awaiting_task=false,
     * which is what the worker sends after the long task finishes.
     */
    const finishWaitingTask = () => {
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 2 },
        });
      });
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Test set generated successfully.',
            awaiting_task: false,
          },
        });
      });
    };

    it('starts with no completed messages and no awaiting flag', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      expect(result.current.isAwaitingTask).toBe(false);
      expect(result.current.messages.every(m => !m.taskCompleted)).toBe(true);
    });

    it('marks the waiting bubble as completed when the task finishes', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      const waitingId = startWaitingThenComplete(result);

      expect(result.current.isAwaitingTask).toBe(true);
      // No bubble is marked completed while the task is still running.
      expect(result.current.messages.every(m => !m.taskCompleted)).toBe(true);

      finishWaitingTask();

      expect(result.current.isAwaitingTask).toBe(false);
      // Marker is set on the bubble that was waiting — NOT on the new
      // streaming bubble that just finalised.
      const waitingBubble = result.current.messages.find(
        m => m.id === waitingId
      );
      expect(waitingBubble?.taskCompleted).toBe(true);
      const otherCompleted = result.current.messages.filter(
        m => m.id !== waitingId && m.taskCompleted
      );
      expect(otherCompleted).toHaveLength(0);
    });

    it('keeps the completed marker on the bubble for the rest of the session', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      const waitingId = startWaitingThenComplete(result);
      finishWaitingTask();
      expect(
        result.current.messages.find(m => m.id === waitingId)?.taskCompleted
      ).toBe(true);

      // Another user turn should not erase the marker on the previous bubble.
      act(() => {
        result.current.sendMessage('Next instruction');
      });
      expect(
        result.current.messages.find(m => m.id === waitingId)?.taskCompleted
      ).toBe(true);

      // A subsequent assistant response (no awaiting_task) also leaves it intact.
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 3 },
        });
      });
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'On it.',
            awaiting_task: false,
          },
        });
      });
      expect(
        result.current.messages.find(m => m.id === waitingId)?.taskCompleted
      ).toBe(true);
    });

    it('does not mark anything when there was no preceding wait', () => {
      // A normal turn (no awaiting_task=true ever set) must not produce
      // a "Done." indicator on the response bubble.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Hello',
            awaiting_task: false,
          },
        });
      });
      expect(result.current.messages.every(m => !m.taskCompleted)).toBe(true);
    });

    it('drops all completion markers when the session changes', () => {
      const { result, rerender } = renderHook(
        ({ sessionId }) => useArchitectChat({ sessionId }),
        { initialProps: { sessionId: 'sess-1' as string | null } }
      );
      const waitingId = startWaitingThenComplete(result);
      finishWaitingTask();
      expect(
        result.current.messages.find(m => m.id === waitingId)?.taskCompleted
      ).toBe(true);

      // Switching sessions clears messages entirely — so by extension
      // there are no leftover taskCompleted markers.
      rerender({ sessionId: 'sess-2' });
      expect(result.current.messages.every(m => !m.taskCompleted)).toBe(true);
      expect(result.current.isAwaitingTask).toBe(false);
    });

    it('marks the second long task complete without disturbing the first marker', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      const firstId = startWaitingThenComplete(result);
      finishWaitingTask();
      expect(
        result.current.messages.find(m => m.id === firstId)?.taskCompleted
      ).toBe(true);

      // A new long-running task starts on a fresh assistant bubble.
      act(() => {
        result.current.sendMessage('Run it again');
      });
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 3 },
        });
      });
      const secondStreaming = result.current.messages.find(
        m => m.isStreaming && m.id !== firstId
      );
      expect(secondStreaming).toBeDefined();
      if (!secondStreaming) {
        throw new Error('Expected a second streaming message');
      }
      const secondId = secondStreaming.id;
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Kicking off generation again…',
            awaiting_task: true,
          },
        });
      });
      // First marker is still on; second isn't completed yet.
      expect(
        result.current.messages.find(m => m.id === firstId)?.taskCompleted
      ).toBe(true);
      expect(
        result.current.messages.find(m => m.id === secondId)?.taskCompleted
      ).toBeFalsy();

      finishWaitingTask();

      // Both bubbles are now marked completed.
      expect(
        result.current.messages.find(m => m.id === firstId)?.taskCompleted
      ).toBe(true);
      expect(
        result.current.messages.find(m => m.id === secondId)?.taskCompleted
      ).toBe(true);
    });
  });

  describe('ARCHITECT_TASK_PROGRESS', () => {
    /**
     * Helper: run the agent through `awaiting_task=true` so that
     * waitingMessageIdRef points at a real bubble. Returns the id of
     * that bubble.
     */
    const arriveAtAwaitingState = (
      result: ReturnType<typeof renderHook>['result']
    ): string => {
      const r = result as unknown as {
        current: ReturnType<typeof useArchitectChat>;
      };
      act(() => {
        r.current.sendMessage('Explore the endpoint');
      });
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 1 },
        });
      });
      const streaming = r.current.messages.find(m => m.isStreaming);
      if (!streaming) throw new Error('expected streaming bubble');
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: 'sess-1',
            content: 'Exploring the endpoint…',
            awaiting_task: true,
          },
        });
      });
      return streaming.id;
    };

    it('routes progress events into streamingState as tool rows (started → active, progress → active, completed → completed)', () => {
      // Progress events are fed into streamingState so they render as
      // tool-call rows in the same bubble — not into message.taskProgress.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      arriveAtAwaitingState(result);

      // First event: started → goes into activeTools
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'started',
            label: 'Starting exploration (domain_probing)',
          },
        });
      });
      expect(result.current.streamingState.activeTools).toHaveLength(1);
      expect(result.current.streamingState.activeTools[0].description).toBe(
        'Starting exploration (domain_probing)'
      );
      expect(result.current.streamingState.completedTools).toHaveLength(0);

      // Second event: progress — previous active entry promoted to completed,
      // new one becomes active.
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'progress',
            label: 'Running domain probing strategy',
          },
        });
      });
      expect(result.current.streamingState.activeTools).toHaveLength(1);
      expect(result.current.streamingState.activeTools[0].description).toBe(
        'Running domain probing strategy'
      );
      expect(result.current.streamingState.completedTools).toHaveLength(1);
      expect(result.current.streamingState.completedTools[0].description).toBe(
        'Starting exploration (domain_probing)'
      );
    });

    it('encodes step and step/total suffixes into description', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      arriveAtAwaitingState(result);

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'progress',
            label: 'Penelope turn',
            step: 3,
            total: 5,
            duration_ms: 1234,
          },
        });
      });

      const active = result.current.streamingState.activeTools[0];
      expect(active.description).toBe('Penelope turn (3/5)');
    });

    it('terminal event lands in completedTools with durationMs', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      arriveAtAwaitingState(result);

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'completed',
            label: 'Exploration completed',
            duration_ms: 4321,
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.completedTools).toHaveLength(1);
      expect(result.current.streamingState.completedTools[0].description).toBe(
        'Exploration completed'
      );
      expect(result.current.streamingState.completedTools[0].durationMs).toBe(
        4321
      );
      expect(result.current.streamingState.completedTools[0].success).toBe(
        true
      );
    });

    it('drops events that arrive before any bubble is awaiting', () => {
      // Without a preceding awaiting_task=true RESPONSE, the hook
      // doesn't know which bubble owns the progress. Drop the event.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'progress',
            label: 'Stray event',
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.completedTools).toHaveLength(0);
    });

    it('ignores events targeting a different session', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      arriveAtAwaitingState(result);

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-other',
            task_id: 'task-1',
            status: 'progress',
            label: 'Should be ignored',
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.completedTools).toHaveLength(0);
    });

    it('ignores malformed events (missing task_id or label)', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      arriveAtAwaitingState(result);

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            // task_id missing
            status: 'progress',
            label: 'No task id',
          },
        });
      });
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'progress',
            // label missing
          },
        });
      });

      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.completedTools).toHaveLength(0);
    });

    it('resumed THINKING closes waiting bubble and opens a fresh streaming bubble', () => {
      // Once the background task finishes and the agent resumes,
      // ARCHITECT_THINKING must:
      //   1. Reset streamingState (clear progress rows)
      //   2. Mark the old waiting bubble as committed (isStreaming=false)
      //   3. Create a NEW streaming bubble so the "Thinking…" indicator
      //      appears immediately while the agent processes the result.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );
      const waitingId = arriveAtAwaitingState(result);

      // Accumulate a progress row.
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_TASK_PROGRESS]({
          type: EventType.ARCHITECT_TASK_PROGRESS,
          payload: {
            session_id: 'sess-1',
            task_id: 'task-1',
            status: 'completed',
            label: 'Exploration done',
            duration_ms: 5000,
          },
        });
      });
      expect(result.current.streamingState.completedTools).toHaveLength(1);

      // Resumed THINKING → old bubble closed out, new bubble created.
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_THINKING]({
          type: EventType.ARCHITECT_THINKING,
          payload: { status: 'thinking', iteration: 2 },
        });
      });

      // streamingState is fresh (progress rows gone, isThinking set).
      expect(result.current.streamingState.completedTools).toHaveLength(0);
      expect(result.current.streamingState.activeTools).toHaveLength(0);
      expect(result.current.streamingState.isThinking).toBe(true);

      // Old waiting bubble is committed.
      const waitingBubble = result.current.messages.find(
        m => m.id === waitingId
      );
      expect(waitingBubble?.isStreaming).toBe(false);

      // A new streaming bubble exists for the resumed turn.
      const newBubble = result.current.messages.find(
        m => m.isStreaming && m.id !== waitingId
      );
      expect(newBubble).toBeDefined();
    });
  });

  describe('completed-plan dismissal (visiblePlan)', () => {
    const COMPLETE_PLAN = '## Plan\n- [x] First\n- [x] Second';
    const COMPLETE_PLAN_V2 = '## Plan\n- [x] First\n- [x] Second\n- [x] Third';
    const INCOMPLETE_PLAN = '## Plan\n- [x] First\n- [ ] Second';

    /**
     * Helper: deliver a plan to the hook via ARCHITECT_RESPONSE.
     * Mirrors what the agent does on every turn — the plan is
     * echoed back even when nothing changed.
     */
    const deliverPlan = (plan: string, sessionId = 'sess-1') => {
      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_RESPONSE]({
          type: EventType.ARCHITECT_RESPONSE,
          payload: {
            session_id: sessionId,
            content: 'Reply',
            plan,
          },
        });
      });
    };

    it('exposes visiblePlan equal to currentPlan when no dismissal happened', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      deliverPlan(COMPLETE_PLAN);

      expect(result.current.currentPlan).toBe(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBe(COMPLETE_PLAN);
    });

    it('hides a completed plan once the user sends another message and the agent re-emits the same plan', () => {
      // Repro of the reported bug:
      //   1. Plan reaches completion → "Plan Complete" badge visible.
      //   2. User types a follow-up message → badge should disappear.
      //   3. Agent's response echoes the same plan markdown → badge
      //      MUST stay hidden (was reappearing before this fix).
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      deliverPlan(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBe(COMPLETE_PLAN);

      act(() => {
        result.current.sendMessage('Thank you!');
      });
      expect(result.current.visiblePlan).toBeNull();

      // Agent echoes the same plan back — must stay dismissed.
      deliverPlan(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBeNull();
      expect(result.current.currentPlan).toBe(COMPLETE_PLAN);
    });

    it('does not dismiss an incomplete plan when the user sends a message', () => {
      // Halfway through planning, the user often asks the agent to
      // tweak something. The badge / progress bar should remain
      // visible so the user can keep tracking what's left to do.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      deliverPlan(INCOMPLETE_PLAN);
      act(() => {
        result.current.sendMessage('Make it broader');
      });
      // currentPlan was cleared on send, but the next response will
      // restore it without dismissal.
      deliverPlan(INCOMPLETE_PLAN);
      expect(result.current.visiblePlan).toBe(INCOMPLETE_PLAN);
    });

    it('un-dismisses when the plan content actually changes', () => {
      // After dismissing a completed plan, if the agent later modifies
      // the plan (e.g. adds more tests), that fresh plan should
      // surface again — the user dismissed *that* completed plan,
      // not all future plans.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      deliverPlan(COMPLETE_PLAN);
      act(() => {
        result.current.sendMessage('Thanks!');
      });
      deliverPlan(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBeNull();

      // Plan grows — even though it's still complete, content differs.
      deliverPlan(COMPLETE_PLAN_V2);
      expect(result.current.visiblePlan).toBe(COMPLETE_PLAN_V2);
    });

    it('un-dismisses when the plan becomes incomplete again', () => {
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      deliverPlan(COMPLETE_PLAN);
      act(() => {
        result.current.sendMessage('Thanks!');
      });
      deliverPlan(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBeNull();

      // New unchecked items appear.
      deliverPlan(INCOMPLETE_PLAN);
      expect(result.current.visiblePlan).toBe(INCOMPLETE_PLAN);
    });

    it('respects a dismissal communicated via ARCHITECT_PLAN_UPDATE', () => {
      // Plan updates can also arrive via the standalone PLAN_UPDATE
      // event, not just via RESPONSE. Same dismissal rules apply.
      const { result } = renderHook(() =>
        useArchitectChat({ sessionId: 'sess-1' })
      );

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_PLAN_UPDATE]({
          type: EventType.ARCHITECT_PLAN_UPDATE,
          payload: { plan: COMPLETE_PLAN },
        });
      });
      expect(result.current.visiblePlan).toBe(COMPLETE_PLAN);

      act(() => {
        result.current.sendMessage('Thanks!');
      });

      act(() => {
        subscriptionHandlers[EventType.ARCHITECT_PLAN_UPDATE]({
          type: EventType.ARCHITECT_PLAN_UPDATE,
          payload: { plan: COMPLETE_PLAN },
        });
      });

      expect(result.current.visiblePlan).toBeNull();
      expect(result.current.currentPlan).toBe(COMPLETE_PLAN);
    });

    it('clears the dismissal on session change', () => {
      const { result, rerender } = renderHook(
        ({ sessionId }) => useArchitectChat({ sessionId }),
        { initialProps: { sessionId: 'sess-1' as string | null } }
      );

      deliverPlan(COMPLETE_PLAN);
      act(() => {
        result.current.sendMessage('Thanks!');
      });
      deliverPlan(COMPLETE_PLAN);
      expect(result.current.visiblePlan).toBeNull();

      rerender({ sessionId: 'sess-2' });
      expect(result.current.currentPlan).toBeNull();
      expect(result.current.visiblePlan).toBeNull();

      // A completed plan in the new session is shown — the previous
      // session's dismissal must not leak across sessions.
      deliverPlan(COMPLETE_PLAN, 'sess-2');
      expect(result.current.visiblePlan).toBe(COMPLETE_PLAN);
    });
  });
});
