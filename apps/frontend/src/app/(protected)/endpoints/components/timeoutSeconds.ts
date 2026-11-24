import { DEFAULT_MAX_TIMEOUT_SECONDS } from '@/constants/endpoint-timeout';

// `max` is the server's MAX_ENDPOINT_TIMEOUT, from useMaxEndpointTimeoutSeconds().

/** Why the Basics step's timeout can't be saved, or null when it can (empty means default). */
export function timeoutSecondsError(
  value: string,
  max: number = DEFAULT_MAX_TIMEOUT_SECONDS
): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isInteger(n) || n < 1 || n > max) {
    return `Enter whole seconds from 1 to ${max}.`;
  }
  return null;
}

/** The timeout as a number, or undefined for the default or an invalid value. */
export function parseTimeoutSeconds(
  value: string,
  max: number = DEFAULT_MAX_TIMEOUT_SECONDS
): number | undefined {
  return value.trim() && timeoutSecondsError(value, max) === null
    ? Number(value.trim())
    : undefined;
}

// The backend's REST default, and the proxy's budget for test calls
// (LONG_RUNNING_TIMEOUT_MS in utils/backend-proxy.ts).
const DEFAULT_TIMEOUT_SECONDS = 30;
const TEST_PROXY_LIMIT_SECONDS = 300;

/** How long a test from the UI can wait at most: the endpoint's timeout, capped by the proxy. */
export function testWaitSeconds(
  value: string,
  max: number = DEFAULT_MAX_TIMEOUT_SECONDS
): number {
  return Math.min(
    parseTimeoutSeconds(value, max) ?? DEFAULT_TIMEOUT_SECONDS,
    TEST_PROXY_LIMIT_SECONDS
  );
}
