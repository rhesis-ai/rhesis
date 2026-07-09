/** Resume a recent Architect session when returning within this window. */
export const ARCHITECT_RESUME_TTL_MS = 15 * 60 * 1000;

export interface ArchitectResumeHint {
  sessionId: string;
  lastActiveAt: number;
}

function storageKey(projectId: string): string {
  return `architect:resume:${projectId}`;
}

export function readResumeHint(
  projectId: string
): ArchitectResumeHint | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = sessionStorage.getItem(storageKey(projectId));
    if (!raw) return null;

    const hint = JSON.parse(raw) as ArchitectResumeHint;
    if (!hint.sessionId || typeof hint.lastActiveAt !== 'number') {
      clearResumeHint(projectId);
      return null;
    }

    if (Date.now() - hint.lastActiveAt > ARCHITECT_RESUME_TTL_MS) {
      clearResumeHint(projectId);
      return null;
    }

    return hint;
  } catch {
    clearResumeHint(projectId);
    return null;
  }
}

export function writeResumeHint(projectId: string, sessionId: string): void {
  if (typeof window === 'undefined') return;

  try {
    const hint: ArchitectResumeHint = {
      sessionId,
      lastActiveAt: Date.now(),
    };
    sessionStorage.setItem(storageKey(projectId), JSON.stringify(hint));
  } catch {
    // sessionStorage may be unavailable in private browsing / SSR
  }
}

export function clearResumeHint(projectId: string): void {
  if (typeof window === 'undefined') return;

  try {
    sessionStorage.removeItem(storageKey(projectId));
  } catch {
    // ignore
  }
}

/** Returns a session id to auto-open, or null when no valid resume hint exists. */
export function pickResumableSessionId(
  projectId: string,
  sessions: Array<{ id: string }>
): string | null {
  const hint = readResumeHint(projectId);
  if (!hint) return null;

  const exists = sessions.some(session => session.id === hint.sessionId);
  if (!exists) {
    clearResumeHint(projectId);
    return null;
  }

  return hint.sessionId;
}
