import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import { isPlanComplete } from '@/utils/architect/plan';
import { readActiveProjectId } from '@/utils/active-project';
import {
  EventType,
  WebSocketMessage,
  ArchitectResponsePayload,
  ArchitectThinkingPayload,
  ArchitectToolPayload,
  ArchitectPlanUpdatePayload,
  ArchitectModeChangePayload,
  ArchitectErrorPayload,
  ArchitectTextChunkPayload,
  ArchitectStreamEndPayload,
  ArchitectTaskProgressPayload,
} from '@/utils/websocket';

export interface ArchitectChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'event';
  content: string;
  timestamp: Date;
  isError?: boolean;
  needsConfirmation?: boolean;
  isStreaming?: boolean;
  /**
   * Set to true on the bubble that owned a long-running "Working…"
   * spinner once that task completes. Persistent — once flipped on,
   * stays on for the rest of the session, so the user can scroll
   * back and still see which step actually finished.
   */
  taskCompleted?: boolean;
  files?: Array<{
    filename: string;
    content_type: string;
    data: string;
    size: number;
  }>;
  mentions?: Array<{
    type: string;
    id: string;
    display: string;
  }>;
}

export interface StreamingState {
  isThinking: boolean;
  currentIteration?: number;
  activeTools: Array<{
    tool: string;
    description?: string;
    args?: Record<string, unknown>;
    reasoning?: string;
    startedAt: number;
  }>;
  completedTools: Array<{
    tool: string;
    description?: string;
    success: boolean;
    preview?: string;
    reasoning?: string;
    durationMs?: number;
    startedAt: number;
  }>;
}

interface UseArchitectChatOptions {
  sessionId: string | null;
  /** Seed the conversation with this user message immediately on mount. */
  initialUserMessage?: string | null;
  /**
   * The project_id the session was created under. Sent with every message so
   * the backend can satisfy the project_isolation RLS policy when looking up
   * the session. Must be the session's own project_id, NOT the currently active
   * project cookie — these can differ when the user switches projects after
   * creating the session.
   */
  sessionProjectId?: string | null;
}

export interface ChatAttachments {
  mentions?: Array<{ type: string; id: string; display: string }>;
  files?: Array<{
    filename: string;
    content_type: string;
    data: string;
    size: number;
  }>;
}

interface UseArchitectChatResult {
  messages: ArchitectChatMessage[];
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  streamingState: StreamingState;
  currentMode: string;
  currentPlan: string | null;
  /**
   * The plan that should currently be visible in the UI. Equal to
   * ``currentPlan`` except when the user has dismissed a completed plan
   * by sending another message — in which case it is ``null`` until
   * the plan content changes again.
   */
  visiblePlan: string | null;
  isAwaitingTask: boolean;
  autoApproveAll: boolean;
  setAutoApproveAll: React.Dispatch<React.SetStateAction<boolean>>;
  setCurrentMode: React.Dispatch<React.SetStateAction<string>>;
  setCurrentPlan: React.Dispatch<React.SetStateAction<string | null>>;
  /** Returns true when the message was handed to the WebSocket, false otherwise. */
  sendMessage: (message: string, attachments?: ChatAttachments) => boolean;
  setMessages: React.Dispatch<React.SetStateAction<ArchitectChatMessage[]>>;
}

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function generateCorrelationId(): string {
  return `corr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

const initialStreamingState: StreamingState = {
  isThinking: false,
  activeTools: [],
  completedTools: [],
};

/**
 * Internal pseudo-tools the agent uses for its own bookkeeping (state
 * persistence, control flow). Surfacing them in the chat tool list is
 * misleading:
 *
 * - `save_plan`: synchronous Pydantic validation — the LLM frequently
 *   fails on the first attempt and self-corrects; showing "Save Plan (fail)
 *   -> Save Plan (ok)" implies a real failure when it's just internal retry.
 * - `await_task`: returns "Turn paused…" — not a user-facing action; it
 *   would render as a completed tool in `ToolCallList` after every
 *   background-task wait.
 *
 * Drop these events at the boundary so neither the active nor the
 * completed list ever sees them. Add new internal tools here as the
 * agent grows.
 */
const HIDDEN_TOOL_NAMES = new Set<string>(['save_plan', 'await_task']);

export function useArchitectChat(
  options: UseArchitectChatOptions
): UseArchitectChatResult {
  const { sessionId, initialUserMessage, sessionProjectId } = options;
  const {
    isConnected,
    send,
    subscribe,
    subscribeToChannel,
    unsubscribeFromChannel,
  } = useWebSocket();

  const [messages, setMessages] = useState<ArchitectChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingState, setStreamingState] = useState<StreamingState>(
    initialStreamingState
  );
  const [currentMode, setCurrentMode] = useState('discovery');
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  // Snapshot of a *complete* plan that the user has dismissed by
  // continuing the conversation. While ``currentPlan === dismissedPlan``,
  // the "Plan Complete" badge stays hidden — re-emitting the same plan
  // markdown on every subsequent ARCHITECT_RESPONSE shouldn't make it
  // pop back. Cleared the moment the plan content changes (new items
  // added, items unchecked, etc.) so a freshly-completed plan does
  // surface again.
  const [dismissedPlan, setDismissedPlan] = useState<string | null>(null);

  // When a new plan arrives, clear the dismissal only if the content
  // has actually changed — same markdown means the agent is re-echoing
  // an already-dismissed plan, which should stay hidden.
  const reconcileDismissedPlan = useCallback((newPlan: string) => {
    setDismissedPlan(prev => (prev !== null && prev !== newPlan ? null : prev));
  }, []);

  const [isAwaitingTask, setIsAwaitingTask] = useState(false);
  const [autoApproveAll, setAutoApproveAll] = useState(false);

  const currentPlanRef = useRef<string | null>(null);
  currentPlanRef.current = currentPlan;

  const pendingCorrelationRef = useRef<string | null>(null);
  const streamingMessageIdRef = useRef<string | null>(null);
  // Holds the id of the assistant bubble that owns the current "Working…"
  // spinner. Captured the moment isAwaitingTask flips true and read again
  // when it flips false so we know which bubble should be marked as
  // taskCompleted. The bubble that was waiting is no longer the "last
  // assistant message" by then (a new streaming bubble has replaced it),
  // so we have to remember it explicitly.
  const waitingMessageIdRef = useRef<string | null>(null);
  const prevAwaitingRef = useRef(false);
  const autoApproveRef = useRef(autoApproveAll);
  autoApproveRef.current = autoApproveAll;
  // Tracks whether the current `error` originated from a denied channel
  // subscription, so a later successful (re)subscribe can clear it without
  // clobbering a genuine ARCHITECT_ERROR. The subscribe effect re-subscribes
  // when sessionProjectId resolves, so a transient empty-project denial may be
  // followed by a successful subscribe.
  const subscriptionDeniedRef = useRef(false);

  // Reset state when switching sessions. Seed the initial user message
  // immediately so it is visible before the WebSocket connection is ready.
  useEffect(() => {
    const seed: ArchitectChatMessage[] = initialUserMessage
      ? [
          {
            id: generateId(),
            role: 'user',
            content: initialUserMessage,
            timestamp: new Date(),
          },
        ]
      : [];
    setMessages(seed);
    setIsLoading(false);
    setError(null);
    setStreamingState(initialStreamingState);
    setCurrentMode('discovery');
    setCurrentPlan(null);
    setDismissedPlan(null);
    setIsAwaitingTask(false);
    streamingMessageIdRef.current = null;
    pendingCorrelationRef.current = null;
    waitingMessageIdRef.current = null;
    prevAwaitingRef.current = false;
    subscriptionDeniedRef.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // When the WebSocket disconnects mid-response, reset isLoading so the
  // chat input re-enables instead of staying frozen.
  const prevIsConnectedRef = useRef(true);
  useEffect(() => {
    const wasConnected = prevIsConnectedRef.current;
    prevIsConnectedRef.current = isConnected;
    if (wasConnected && !isConnected && isLoading) {
      setIsLoading(false);
      setStreamingState(initialStreamingState);
      pendingCorrelationRef.current = null;
    }
  }, [isConnected, isLoading]);

  // Permanently mark the bubble whose task just completed with
  // taskCompleted: true. Triggered on the falling edge of isAwaitingTask
  // using the message id captured when the spinner was first shown. The
  // marker stays on the message for the rest of the session so the user
  // can scroll back and still see which step actually finished.
  useEffect(() => {
    if (isAwaitingTask) {
      prevAwaitingRef.current = true;
      return;
    }
    if (!prevAwaitingRef.current) {
      return;
    }
    prevAwaitingRef.current = false;
    const id = waitingMessageIdRef.current;
    if (!id) return;
    waitingMessageIdRef.current = null;
    setMessages(prev =>
      prev.map(m => (m.id === id ? { ...m, taskCompleted: true } : m))
    );
  }, [isAwaitingTask]);

  // Subscribe to architect channel when session changes. The cleanup
  // unsubscribes from the previous channel so the server stops forwarding
  // events for the old session — without this, streaming output from the
  // previous session bleeds into the newly opened tab.
  useEffect(() => {
    if (!sessionId || !isConnected) return;

    const channel = `architect:${sessionId}`;
    // Pass the session's project_id so the backend's subscribe-time
    // authorization lookup can satisfy the fail-closed project_isolation RLS
    // policy. Without it the lookup runs with a blank project and cannot see
    // the project-scoped session, denying the subscription and leaving the
    // chat stuck on "Thinking…". sessionProjectId is included in the deps so
    // we re-subscribe once it resolves from the async-loaded session list.
    subscribeToChannel(channel, sessionProjectId);
    return () => {
      unsubscribeFromChannel(channel);
    };
  }, [
    sessionId,
    isConnected,
    sessionProjectId,
    subscribeToChannel,
    unsubscribeFromChannel,
  ]);

  // Subscribe to all architect event types
  useEffect(() => {
    const unsubs: Array<() => void> = [];

    // Helper: ensure a streaming assistant message exists, return its ID
    const ensureStreamingMessage = (): string => {
      if (streamingMessageIdRef.current) return streamingMessageIdRef.current;
      const msgId = generateId();
      streamingMessageIdRef.current = msgId;
      const msg: ArchitectChatMessage = {
        id: msgId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages(prev => [...prev, msg]);
      return msgId;
    };

    unsubs.push(
      subscribe(EventType.ARCHITECT_THINKING, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectThinkingPayload;
        if (payload?.session_id && payload.session_id !== sessionId) return;

        // If we were awaiting a background task, close out the waiting
        // bubble on the *first* THINKING of the resumed turn only.
        //
        // While awaiting, streamingMessageIdRef === waitingMessageIdRef
        // (the same bubble owns both). The moment we create a new bubble
        // they diverge. Use that equality as the "first resumed THINKING"
        // signal so that subsequent THINKINGs (higher iterations of the
        // same resumed turn) don't re-enter this path, orphan the
        // already-created bubble, and leave an empty isStreaming=true ghost.
        const prevWaitingId = waitingMessageIdRef.current;
        const isFirstResumedThinking =
          !!prevWaitingId && streamingMessageIdRef.current === prevWaitingId;
        if (isFirstResumedThinking) {
          setStreamingState(initialStreamingState);
          // Mark the waiting bubble as committed. taskCompleted is stamped
          // here as an early signal; the isAwaitingTask falling-edge
          // useEffect is the canonical mechanism and owns the ref cleanup —
          // deliberately NOT clearing waitingMessageIdRef here so the
          // effect can still fire.
          setMessages(prev =>
            prev.map(m =>
              m.id === prevWaitingId
                ? { ...m, isStreaming: false, taskCompleted: true }
                : m
            )
          );
          streamingMessageIdRef.current = null;
        }

        ensureStreamingMessage();
        setIsAwaitingTask(false);
        setStreamingState(prev => ({
          ...prev,
          isThinking: true,
          currentIteration: payload?.iteration ?? prev.currentIteration,
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_STREAM_START, (msg: WebSocketMessage) => {
        // Defensive session_id guard: the payload type doesn't currently
        // declare session_id, but if the backend includes it (or starts to),
        // this prevents bleed during the brief unsubscribe race window.
        const sid = (msg.payload as { session_id?: string } | undefined)
          ?.session_id;
        if (sid && sid !== sessionId) return;
        // Message already created by THINKING; just ensure it exists
        ensureStreamingMessage();
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TEXT_CHUNK, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectTextChunkPayload;
        const streamId = streamingMessageIdRef.current;
        if (!streamId || !payload?.chunk) return;

        setMessages(prev =>
          prev.map(m =>
            m.id === streamId ? { ...m, content: m.content + payload.chunk } : m
          )
        );
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_STREAM_END, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectStreamEndPayload;
        const streamId = streamingMessageIdRef.current;

        if (streamId && payload) {
          setMessages(prev =>
            prev.map(m =>
              m.id === streamId
                ? {
                    ...m,
                    content: payload.error
                      ? m.content || payload.content
                      : m.content,
                    isError: Boolean(payload.error?.trim()),
                  }
                : m
            )
          );
        }
        // Don't clear streamingMessageIdRef yet — wait for ARCHITECT_RESPONSE
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_RESPONSE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectResponsePayload;
        if (payload?.session_id !== sessionId) return;

        setIsLoading(false);
        setError(null);
        pendingCorrelationRef.current = null;

        if (payload.mode) setCurrentMode(payload.mode);
        if (payload.plan) {
          setCurrentPlan(payload.plan);
          reconcileDismissedPlan(payload.plan);
        }
        const streamId = streamingMessageIdRef.current;
        if (payload.awaiting_task && streamId) {
          // Remember which bubble owns the progress trail so that
          // ARCHITECT_THINKING can close it out when the task resumes.
          waitingMessageIdRef.current = streamId;
        }
        setIsAwaitingTask(payload.awaiting_task ?? false);

        if (streamId) {
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== streamId) return m;
              const content = m.content.trim()
                ? m.content
                : payload.content || '';
              return {
                ...m,
                content,
                isError: false,
                // When awaiting a background task, keep isStreaming=true so
                // ArchitectChat continues passing streamingState to this bubble —
                // task-progress events will append rows to it just like tool calls.
                // The ARCHITECT_THINKING handler resets isStreaming when the
                // resumed turn begins.
                isStreaming: payload.awaiting_task ? true : false,
                needsConfirmation: payload.needs_confirmation ?? false,
              };
            })
          );
          if (!payload.awaiting_task) {
            // Normal response: clear the streaming message ref and reset state.
            streamingMessageIdRef.current = null;
            setStreamingState(initialStreamingState);
          }
          // When awaiting_task=true we deliberately keep streamingMessageIdRef
          // pointing at the waiting bubble so ARCHITECT_THINKING knows to close
          // it when the task completes.
        } else {
          // Fallback: no streaming message exists (backward compatibility).
          // If awaiting_task=true we still need to mark the message as
          // streaming and register it as the waiting bubble so that
          // ARCHITECT_TASK_PROGRESS events can attach to it.
          const fallbackId = generateId();
          const assistantMessage: ArchitectChatMessage = {
            id: fallbackId,
            role: 'assistant',
            content: payload.content || '',
            timestamp: new Date(),
            needsConfirmation: payload.needs_confirmation ?? false,
            isStreaming: payload.awaiting_task ? true : undefined,
          };
          setMessages(prev => [...prev, assistantMessage]);
          if (payload.awaiting_task) {
            streamingMessageIdRef.current = fallbackId;
            waitingMessageIdRef.current = fallbackId;
          } else {
            setStreamingState(initialStreamingState);
          }
        }
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TOOL_START, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectToolPayload;
        if (!payload?.tool) return;
        if (HIDDEN_TOOL_NAMES.has(payload.tool)) return;
        setStreamingState(prev => ({
          ...prev,
          activeTools: [
            ...prev.activeTools,
            {
              tool: payload.tool,
              description: payload.description,
              args: payload.args,
              reasoning: payload.reasoning,
              startedAt: Date.now(),
            },
          ],
        }));
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TOOL_END, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectToolPayload;
        if (!payload?.tool) return;
        if (HIDDEN_TOOL_NAMES.has(payload.tool)) return;
        setStreamingState(prev => {
          const activeTool = prev.activeTools.find(
            t => t.tool === payload.tool
          );
          const clientDuration = activeTool
            ? Date.now() - activeTool.startedAt
            : undefined;
          const durationMs = payload.duration_ms ?? clientDuration;
          return {
            ...prev,
            activeTools: prev.activeTools.filter(t => t.tool !== payload.tool),
            completedTools: [
              ...prev.completedTools,
              {
                tool: payload.tool,
                description: payload.description,
                success: payload.success ?? true,
                preview: payload.preview,
                reasoning: activeTool?.reasoning || payload.reasoning,
                durationMs,
                startedAt: activeTool?.startedAt ?? Date.now(),
              },
            ],
          };
        });
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_PLAN_UPDATE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectPlanUpdatePayload;
        if (payload?.plan) {
          setCurrentPlan(payload.plan);
          reconcileDismissedPlan(payload.plan);
        }
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_MODE_CHANGE, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectModeChangePayload;
        if (payload?.new_mode) setCurrentMode(payload.new_mode);
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_TASK_PROGRESS, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectTaskProgressPayload;
        if (payload?.session_id && payload.session_id !== sessionId) return;
        if (!payload?.task_id || !payload?.label) return;

        // The waiting bubble's streamingState is kept alive by the
        // ARCHITECT_RESPONSE handler (awaiting_task=true). Route progress
        // entries directly into streamingState so they render as tool-call
        // rows inside that same bubble — identical visual to regular tool
        // calls. If the guard ref is unset (event arrived before RESPONSE),
        // drop the event rather than guess at the wrong bubble.
        if (!waitingMessageIdRef.current) return;

        const description =
          payload.step !== undefined && payload.total !== undefined
            ? `${payload.label} (${payload.step}/${payload.total})`
            : payload.step !== undefined
              ? `${payload.label} (${payload.step})`
              : payload.label;

        const isLive =
          payload.status === 'started' || payload.status === 'progress';

        setStreamingState(prev => {
          // Promote any previous active entry for this task to completed —
          // only one entry per task can be active at a time.
          const promoted: StreamingState['completedTools'] = prev.activeTools
            .filter(t => t.tool === payload.task_id)
            .map(t => ({
              tool: t.tool,
              description: t.description,
              success: true,
              startedAt: t.startedAt,
            }));
          const stillActive = prev.activeTools.filter(
            t => t.tool !== payload.task_id
          );

          const newEntry: StreamingState['completedTools'][number] = {
            tool: payload.task_id,
            description,
            success: payload.status !== 'failed',
            durationMs: payload.duration_ms,
            startedAt: Date.now(),
          };

          return {
            ...prev,
            activeTools: isLive
              ? [
                  ...stillActive,
                  {
                    tool: payload.task_id,
                    description,
                    startedAt: Date.now(),
                  },
                ]
              : stillActive,
            completedTools: isLive
              ? [...prev.completedTools, ...promoted]
              : [...prev.completedTools, ...promoted, newEntry],
          };
        });
      })
    );

    unsubs.push(
      subscribe(EventType.ARCHITECT_ERROR, (msg: WebSocketMessage) => {
        const payload = msg.payload as unknown as ArchitectErrorPayload;
        if (payload?.session_id && payload.session_id !== sessionId) return;

        setIsLoading(false);
        setStreamingState(initialStreamingState);
        pendingCorrelationRef.current = null;

        const errorMsg = payload?.error || 'An error occurred';
        setError(errorMsg);

        setMessages(prev => [
          ...prev,
          {
            id: generateId(),
            role: 'assistant',
            content: errorMsg,
            timestamp: new Date(),
            isError: true,
          },
        ]);
      })
    );

    // A denied channel subscription means no architect events will ever arrive
    // for this session. Surface it and stop waiting instead of hanging on the
    // "Thinking…" spinner forever. Scoped to this session's channel so denials
    // for other channels are ignored.
    unsubs.push(
      subscribe(EventType.SUBSCRIPTION_ERROR, (msg: WebSocketMessage) => {
        const payload = msg.payload as
          | { channel?: string; error?: string }
          | undefined;
        const deniedChannel = payload?.channel ?? msg.channel;
        if (deniedChannel !== `architect:${sessionId}`) return;

        setIsLoading(false);
        setStreamingState(initialStreamingState);
        pendingCorrelationRef.current = null;

        subscriptionDeniedRef.current = true;
        const errorMsg = payload?.error || 'Could not connect to this session';
        setError(errorMsg);
      })
    );

    // A successful (re)subscribe clears a prior subscription-denial error —
    // the subscribe effect retries once sessionProjectId resolves, so an early
    // empty-project denial shouldn't leave a stale alert on screen.
    unsubs.push(
      subscribe(EventType.SUBSCRIBED, (msg: WebSocketMessage) => {
        if (msg.channel !== `architect:${sessionId}`) return;
        if (subscriptionDeniedRef.current) {
          subscriptionDeniedRef.current = false;
          setError(null);
        }
      })
    );

    return () => unsubs.forEach(fn => fn());
  }, [reconcileDismissedPlan, subscribe, sessionId]);

  const sendMessage = useCallback(
    (message: string, attachments?: ChatAttachments): boolean => {
      if (!sessionId || !isConnected || isLoading) return false;

      const trimmed = message.trim();
      if (!trimmed) return false;

      setError(null);
      setIsAwaitingTask(false);
      waitingMessageIdRef.current = null;
      prevAwaitingRef.current = false;

      if (currentPlanRef.current && isPlanComplete(currentPlanRef.current)) {
        // Once the plan is fully checked off, sending another message
        // means the user has acknowledged completion — remember the
        // dismissed plan so the badge doesn't pop back when the next
        // ARCHITECT_RESPONSE re-emits the same markdown.
        setDismissedPlan(currentPlanRef.current);
        setCurrentPlan(null);
      }

      const correlationId = generateCorrelationId();
      pendingCorrelationRef.current = correlationId;

      setMessages(prev => {
        // Don't duplicate a message that was already seeded (e.g. from welcome screen)
        const last = prev[prev.length - 1];
        if (last?.role === 'user' && last.content === trimmed) return prev;
        return [
          ...prev,
          {
            id: generateId(),
            role: 'user',
            content: trimmed,
            timestamp: new Date(),
            files: attachments?.files,
            mentions: attachments?.mentions,
          },
        ];
      });

      setIsLoading(true);
      setStreamingState(initialStreamingState);

      const payload: Record<string, unknown> = {
        session_id: sessionId,
        message: trimmed,
      };
      // Use the session's own project_id (not the currently active project
      // cookie) so the backend can find the session under project_isolation RLS.
      // The two may differ when the user switches projects after creating the
      // session; sending the wrong project_id causes a "Session not found" error.
      const projectId = sessionProjectId ?? readActiveProjectId();
      if (projectId) {
        payload.project_id = projectId;
      }
      if (attachments) {
        payload.attachments = attachments;
      }
      if (autoApproveRef.current) {
        payload.auto_approve = true;
      }

      const sent = send({
        type: EventType.ARCHITECT_MESSAGE,
        correlation_id: correlationId,
        payload,
      });

      if (!sent) {
        setIsLoading(false);
        setError('Failed to send message');
        pendingCorrelationRef.current = null;
        return false;
      }
      return true;
    },
    [sessionId, sessionProjectId, isConnected, isLoading, send]
  );

  const visiblePlan = useMemo(
    () => (currentPlan && currentPlan === dismissedPlan ? null : currentPlan),
    [currentPlan, dismissedPlan]
  );

  return {
    messages,
    isLoading,
    error,
    isConnected,
    streamingState,
    currentMode,
    currentPlan,
    visiblePlan,
    isAwaitingTask,
    autoApproveAll,
    setAutoApproveAll,
    setCurrentMode,
    setCurrentPlan,
    sendMessage,
    setMessages,
  };
}
