// Same bounds as the backend's _check_timeout_seconds.
export const MAX_TIMEOUT_SECONDS = 3600;

/** Why the Basics step's timeout can't be saved, or null when it can (empty means default). */
export function timeoutSecondsError(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isInteger(n) || n < 1 || n > MAX_TIMEOUT_SECONDS) {
    return `Enter whole seconds from 1 to ${MAX_TIMEOUT_SECONDS}.`;
  }
  return null;
}

/** The timeout as a number, or undefined for the default or an invalid value. */
export function parseTimeoutSeconds(value: string): number | undefined {
  return value.trim() && timeoutSecondsError(value) === null
    ? Number(value.trim())
    : undefined;
}

// The backend's REST default, and the proxy's budget for test calls
// (LONG_RUNNING_TIMEOUT_MS in utils/backend-proxy.ts).
const DEFAULT_TIMEOUT_SECONDS = 30;
const TEST_PROXY_LIMIT_SECONDS = 300;

/** How long a test from the UI can wait at most: the endpoint's timeout, capped by the proxy. */
export function testWaitSeconds(value: string): number {
  return Math.min(
    parseTimeoutSeconds(value) ?? DEFAULT_TIMEOUT_SECONDS,
    TEST_PROXY_LIMIT_SECONDS
  );
}
