/**
 * The backend's default MAX_ENDPOINT_TIMEOUT. Only a fallback for when
 * `GET /features` hasn't answered or predates the field; read the real ceiling
 * with `useMaxEndpointTimeoutSeconds()`.
 */
export const DEFAULT_MAX_TIMEOUT_SECONDS = 7200;

/**
 * The backend's call timeout per connection type when an endpoint sets none.
 * Fallback only; read the server's values with `useDefaultEndpointTimeoutSeconds()`.
 */
export const DEFAULT_ENDPOINT_TIMEOUT_SECONDS: Readonly<
  Record<string, number>
> = { REST: 30, WebSocket: 30, SDK: 120 };

/**
 * How long the frontend proxy waits for a slow backend call, including UI
 * endpoint tests. Runs are not affected; they wait the endpoint's full timeout.
 */
export const LONG_REQUEST_LIMIT_SECONDS = 300;
