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

/**
 * How a client-credentials endpoint sends its client ID and secret to the
 * token URL (RFC 7591 names), matching the backend TokenEndpointAuthMethod enum.
 */
export const TOKEN_ENDPOINT_AUTH_METHODS = {
  CLIENT_SECRET_BASIC: 'client_secret_basic',
  CLIENT_SECRET_POST: 'client_secret_post',
} as const;

export type TokenEndpointAuthMethod =
  (typeof TOKEN_ENDPOINT_AUTH_METHODS)[keyof typeof TOKEN_ENDPOINT_AUTH_METHODS];

export const TOKEN_ENDPOINT_AUTH_METHOD_LABELS: Record<
  TokenEndpointAuthMethod,
  string
> = {
  [TOKEN_ENDPOINT_AUTH_METHODS.CLIENT_SECRET_BASIC]: 'Basic auth header',
  [TOKEN_ENDPOINT_AUTH_METHODS.CLIENT_SECRET_POST]: 'In request body',
};

export const ENDPOINT_AUTH_TYPE_LABELS: Record<EndpointAuthType, string> = {
  [ENDPOINT_AUTH_TYPES.BEARER_TOKEN]: 'Bearer token',
  [ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS]: 'OAuth 2.0 client credentials',
};
