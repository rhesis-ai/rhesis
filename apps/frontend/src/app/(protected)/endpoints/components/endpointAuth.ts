import {
  ENDPOINT_AUTH_TYPES,
  type EndpointAuthType,
} from '@/constants/endpoint-auth';
import type {
  Endpoint,
  EndpointEditData,
  EndpointTestRequest,
} from '@/utils/api-client/interfaces/endpoint';

/** Client-credentials fields as the form edits them: everything is text. */
export interface ClientCredentialsDraft {
  token_url: string;
  client_id: string;
  // '' keeps the stored secret
  client_secret: string;
  audience: string;
  // space-separated
  scopes: string;
  // JSON object text, '' for none
  extra_payload: string;
}

export const EMPTY_CLIENT_CREDENTIALS: ClientCredentialsDraft = {
  token_url: '',
  client_id: '',
  client_secret: '',
  audience: '',
  scopes: '',
  extra_payload: '',
};

export function authTypeOf(endpoint: Pick<Endpoint, 'auth_type'>) {
  return endpoint.auth_type === ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS
    ? ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS
    : ENDPOINT_AUTH_TYPES.BEARER_TOKEN;
}

export function clientCredentialsFromEndpoint(
  endpoint: Endpoint
): ClientCredentialsDraft {
  return {
    token_url: endpoint.token_url || '',
    client_id: endpoint.client_id || '',
    client_secret: '',
    audience: endpoint.audience || '',
    scopes: (endpoint.scopes || []).join(' '),
    extra_payload:
      endpoint.extra_payload && Object.keys(endpoint.extra_payload).length > 0
        ? JSON.stringify(endpoint.extra_payload, null, 2)
        : '',
  };
}

function isValidUrl(url: string) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export function parseScopes(scopes: string): string[] {
  return scopes.split(/\s+/).filter(Boolean);
}

/** Parses extra payload text; the token request is form-encoded, so values must be strings. */
export function parseExtraPayload(
  text: string
): { value: Record<string, string> | null } | { error: string } {
  if (!text.trim()) return { value: null };
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { error: 'Extra payload must be valid JSON' };
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { error: 'Extra payload must be a JSON object' };
  }
  for (const [key, entry] of Object.entries(parsed)) {
    if (typeof entry !== 'string') {
      return { error: `Extra payload: "${key}" must be a string value` };
    }
  }
  return { value: parsed as Record<string, string> };
}

/** First problem with the client-credentials fields, or null when they can be saved. */
export function validateClientCredentials(
  draft: ClientCredentialsDraft,
  hasStoredSecret: boolean
): string | null {
  if (!draft.token_url.trim()) return 'Token URL is required';
  if (!isValidUrl(draft.token_url.trim())) return 'Enter a valid token URL';
  if (!draft.client_id.trim()) return 'Client ID is required';
  if (!draft.client_secret && !hasStoredSecret)
    return 'Client secret is required';
  const extra = parseExtraPayload(draft.extra_payload);
  return 'error' in extra ? extra.error : null;
}

/** The auth fields to send for a save. Call only after validation passed. */
export function authPayload(
  authType: EndpointAuthType,
  draft: ClientCredentialsDraft
): EndpointEditData {
  if (authType !== ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS) {
    return { auth_type: authType };
  }
  const extra = parseExtraPayload(draft.extra_payload);
  const scopes = parseScopes(draft.scopes);
  const payload: EndpointEditData = {
    auth_type: authType,
    token_url: draft.token_url.trim(),
    client_id: draft.client_id.trim(),
    audience: draft.audience.trim() || null,
    scopes: scopes.length > 0 ? scopes : null,
    extra_payload: 'value' in extra ? extra.value : null,
  };
  if (draft.client_secret) payload.client_secret = draft.client_secret;
  return payload;
}

/** The auth part of a POST /endpoints/test body for an unsaved endpoint. */
export function testAuthFields(
  authType: EndpointAuthType,
  authToken: string,
  draft: ClientCredentialsDraft
): Pick<
  EndpointTestRequest,
  | 'auth_type'
  | 'auth_token'
  | 'token_url'
  | 'client_id'
  | 'client_secret'
  | 'audience'
  | 'scopes'
  | 'extra_payload'
> {
  if (authType !== ENDPOINT_AUTH_TYPES.CLIENT_CREDENTIALS) {
    return { auth_type: authType, auth_token: authToken };
  }
  const extra = parseExtraPayload(draft.extra_payload);
  const scopes = parseScopes(draft.scopes);
  return {
    auth_type: authType,
    token_url: draft.token_url.trim(),
    client_id: draft.client_id.trim(),
    client_secret: draft.client_secret,
    audience: draft.audience.trim() || undefined,
    scopes: scopes.length > 0 ? scopes : undefined,
    extra_payload: 'value' in extra && extra.value ? extra.value : undefined,
  };
}
