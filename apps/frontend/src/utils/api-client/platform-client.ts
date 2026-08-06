import type { PlatformKeyStatus } from './interfaces/platform';

/**
 * Typed client for the deployment-wide Rhesis platform API key.
 *
 * Unlike the entity clients (which extend `BaseApiClient` and route through the
 * generic `/api/backend` proxy), these call the dedicated same-origin BFF route
 * at `/api/platform/rhesis-key`, which injects the bearer token server-side and
 * passes backend 404s through cleanly (the endpoints only exist in local mode).
 */

const PLATFORM_KEY_ROUTE = '/api/platform/rhesis-key';

/** Thrown when the platform-key BFF route returns a non-2xx response. */
export class PlatformKeyError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'PlatformKeyError';
    this.status = status;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data: unknown = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data
        ? (data as { detail?: unknown }).detail
        : undefined;
    const message =
      typeof detail === 'string' && detail
        ? detail
        : `Request failed with status ${response.status}`;
    throw new PlatformKeyError(message, response.status);
  }

  return data as T;
}

export async function getRhesisPlatformKeyStatus(): Promise<PlatformKeyStatus> {
  const response = await fetch(PLATFORM_KEY_ROUTE, { method: 'GET' });
  return parseResponse<PlatformKeyStatus>(response);
}

export async function setRhesisPlatformKey(
  key: string
): Promise<PlatformKeyStatus> {
  const response = await fetch(PLATFORM_KEY_ROUTE, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key }),
  });
  return parseResponse<PlatformKeyStatus>(response);
}

export async function clearRhesisPlatformKey(): Promise<PlatformKeyStatus> {
  const response = await fetch(PLATFORM_KEY_ROUTE, { method: 'DELETE' });
  return parseResponse<PlatformKeyStatus>(response);
}
