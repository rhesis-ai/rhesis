/**
 * The backend's default MAX_ENDPOINT_TIMEOUT. Only a fallback for when
 * `GET /features` hasn't answered or predates the field; read the real ceiling
 * with `useMaxEndpointTimeoutSeconds()`.
 */
export const DEFAULT_MAX_TIMEOUT_SECONDS = 7200;
