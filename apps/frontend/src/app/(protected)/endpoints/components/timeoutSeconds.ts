import {
  DEFAULT_ENDPOINT_TIMEOUT_SECONDS,
  DEFAULT_MAX_TIMEOUT_SECONDS,
  LONG_REQUEST_LIMIT_SECONDS,
} from '@/constants/endpoint-timeout';

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

/** How long one call may take: the endpoint's timeout, else its connection type's default. */
export function endpointTimeoutSeconds(
  value: string,
  max: number = DEFAULT_MAX_TIMEOUT_SECONDS,
  defaultSeconds: number = DEFAULT_ENDPOINT_TIMEOUT_SECONDS.REST
): number {
  return parseTimeoutSeconds(value, max) ?? defaultSeconds;
}

/** How long a test from the UI can wait at most: the endpoint's timeout, capped by the proxy. */
export function testWaitSeconds(
  value: string,
  max: number = DEFAULT_MAX_TIMEOUT_SECONDS,
  defaultSeconds: number = DEFAULT_ENDPOINT_TIMEOUT_SECONDS.REST
): number {
  return Math.min(
    endpointTimeoutSeconds(value, max, defaultSeconds),
    LONG_REQUEST_LIMIT_SECONDS
  );
}
