import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  ArchitectSession,
  ArchitectSessionCreateRequest,
} from '@/utils/api-client/architect-client';

export interface CreateAndOpenArchitectSessionOptions {
  title: string;
  initialMessage: string;
  /** Open in a new tab (default true). Falls back to same-tab if blocked. */
  newTab?: boolean;
  /** Test seams */
  openWindow?: (url?: string, target?: string) => Window | null;
  navigate?: (url: string) => void;
  storage?: Storage | null;
}

const PENDING_HANDOFF_PREFIX = 'architect:pendingHandoff:';
// Guard against replaying a stale message if the handoff tab never opened
// (e.g. popup blocked and the user navigated away before consuming it).
const PENDING_HANDOFF_TTL_MS = 5 * 60 * 1000;

interface PendingHandoffEnvelope {
  message: string;
  createdAt: number;
}

function resolveStorage(explicit?: Storage | null): Storage | null {
  if (explicit) return explicit;
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/**
 * Persist the handoff's initial message keyed by session id so the newly
 * opened `/architect?session=<id>` tab can pick it up and send it over the
 * WebSocket itself. localStorage is shared across same-origin tabs, so the
 * value written here is immediately readable in the new tab.
 */
export function stashPendingHandoffMessage(
  sessionId: string,
  message: string,
  storage?: Storage | null
): void {
  const store = resolveStorage(storage);
  if (!store) return;
  try {
    store.setItem(
      `${PENDING_HANDOFF_PREFIX}${sessionId}`,
      JSON.stringify({ message, createdAt: Date.now() })
    );
  } catch {
    // Ignore quota/serialization errors — the handoff still works via the
    // normal empty-session path, just without an auto-sent first message.
  }
}

/**
 * Read (without removing) the pending handoff message for a session. Returns
 * null when absent, expired, or unreadable.
 *
 * Reading is deliberately non-destructive: the entry is removed only once the
 * message has actually been sent (see `clearPendingHandoffMessage`). This keeps
 * it single-use *at send time*, so a failed session lookup leaves the message
 * available for a retry, and a message that was already sent is never resent.
 */
export function peekPendingHandoffMessage(
  sessionId: string,
  storage?: Storage | null
): string | null {
  const store = resolveStorage(storage);
  if (!store) return null;
  let raw: string | null;
  try {
    raw = store.getItem(`${PENDING_HANDOFF_PREFIX}${sessionId}`);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as PendingHandoffEnvelope;
    if (!parsed?.message) return null;
    if (Date.now() - (parsed.createdAt ?? 0) > PENDING_HANDOFF_TTL_MS) {
      return null;
    }
    return parsed.message;
  } catch {
    return null;
  }
}

/** Remove the pending handoff message for a session (call after it is sent). */
export function clearPendingHandoffMessage(
  sessionId: string,
  storage?: Storage | null
): void {
  const store = resolveStorage(storage);
  if (!store) return;
  try {
    store.removeItem(`${PENDING_HANDOFF_PREFIX}${sessionId}`);
  } catch {
    // Best effort.
  }
}

/**
 * Read and remove the pending handoff message in one step (single-use). Prefer
 * `peekPendingHandoffMessage` + `clearPendingHandoffMessage` when the removal
 * should be tied to the message actually being sent.
 */
export function takePendingHandoffMessage(
  sessionId: string,
  storage?: Storage | null
): string | null {
  const message = peekPendingHandoffMessage(sessionId, storage);
  if (message !== null) {
    clearPendingHandoffMessage(sessionId, storage);
  }
  return message;
}

/**
 * Create an empty Architect session and navigate to
 * `/architect?session=<id>`, stashing the initial message so the opened tab
 * sends it over the WebSocket once connected.
 *
 * The message is deliberately NOT passed as the backend `initial_message`:
 * that would start the Celery turn at creation time, before the new tab has
 * connected and subscribed to `architect:{id}`, so the streaming events would
 * be missed and the Architect would appear idle until the user sent another
 * message. Routing through the tab's own WebSocket send guarantees it is
 * connected and subscribed before the turn starts (mirrors the welcome-screen
 * flow, which the backend acknowledges directly to the initiating connection).
 *
 * Opens `about:blank` synchronously on the click gesture so browsers do not
 * popup-block the tab after the async create call.
 */
export async function createAndOpenArchitectSession(
  options: CreateAndOpenArchitectSessionOptions
): Promise<ArchitectSession> {
  const { title, initialMessage } = options;
  const newTab = options.newTab !== false;
  const openWindow =
    options.openWindow ??
    (typeof window !== 'undefined' ? window.open.bind(window) : undefined);
  const navigate =
    options.navigate ??
    (typeof window !== 'undefined'
      ? (url: string) => {
          window.location.assign(url);
        }
      : undefined);

  let tab: Window | null = null;
  if (newTab && openWindow) {
    tab = openWindow('about:blank', '_blank');
  }

  try {
    const client = new ApiClientFactory().getArchitectClient();
    const payload: ArchitectSessionCreateRequest = {
      title,
    };
    const session = await client.createSession(payload);
    stashPendingHandoffMessage(session.id, initialMessage, options.storage);
    const url = `/architect?session=${encodeURIComponent(session.id)}`;

    if (tab && !tab.closed) {
      tab.location.href = url;
    } else if (navigate) {
      navigate(url);
    }

    return session;
  } catch (error) {
    if (tab && !tab.closed) {
      tab.close();
    }
    throw error;
  }
}
