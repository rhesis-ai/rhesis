/**
 * Endpoint auth types, matching the backend EndpointAuthType enum.
 * Keep in step with apps/backend/src/rhesis/backend/app/models/enums.py.
 */
export const ENDPOINT_AUTH_TYPES = {
  BEARER_TOKEN: 'bearer_token',
  CLIENT_CREDENTIALS: 'client_credentials',
} as const;

export type EndpointAuthType =
  (typeof ENDPOINT_AUTH_TYPES)[keyof typeof ENDPOINT_AUTH_TYPES];

export const ENDPOINT_AUTH_TYPE_LABELS: Record<EndpointAuthType, string> = {
  [ENDPOINT_AUTH_TYPES.BEARER_TOKEN]: 'Bearer token',
  [ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS]: 'OAuth 2.0 client credentials',
};
