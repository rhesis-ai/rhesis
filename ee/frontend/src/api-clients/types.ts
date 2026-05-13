/**
 * Frontend types for the API Clients feature.
 *
 * Mirrors the backend Pydantic schemas at
 * `ee/backend/src/rhesis/backend/ee/api_clients/schemas.py`. Keep in
 * sync when adding fields. The two schemas exist as separate types
 * because the security-relevant difference between them is what makes
 * the contract correct:
 *
 * - `AuthClient` is the read shape -- it physically does NOT contain
 *   `client_secret`, so even a buggy component that JSON-stringifies a
 *   row cannot leak the secret through this type.
 * - `AuthClientCreated` is the one-shot create / rotate response that
 *   carries the plaintext secret. The UI shows it once, requires the
 *   user to acknowledge, and never persists it.
 *
 * The set of supported scopes is duplicated here from the backend
 * `V1_SUPPORTED_SCOPES` constant so the frontend's create form can
 * render scope choices without round-tripping a config endpoint. This
 * is a known dual-source-of-truth -- the backend's validator is the
 * authority; the frontend just narrows the options the admin sees.
 */

/** Coarse v1 scopes (mirror of backend `V1_SUPPORTED_SCOPES`). */
export const V1_SUPPORTED_SCOPES = ['read', 'full', 'offline_access'] as const;
export type V1Scope = (typeof V1_SUPPORTED_SCOPES)[number];

/**
 * Read-side AuthClient row. Returned by GET (list, detail) and the
 * enable / disable endpoints. Never carries the secret.
 */
export interface AuthClient {
  id: string;
  organization_id: string;
  client_id: string;
  name: string | null;
  expected_subject_azp: string;
  expected_subject_audience: string | null;
  allowed_scopes: string[];
  default_scope: string;
  /** ISO-8601 timestamp; bumping it invalidates issued tokens. */
  token_epoch: string;
  disabled: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * One-shot response from `POST /organizations/{id}/auth-clients` and
 * `POST /organizations/{id}/auth-clients/{id}/rotate`. The `client_secret`
 * field appears here and ONLY here.
 */
export interface AuthClientCreated extends AuthClient {
  client_secret: string;
}

/**
 * Request body for `POST /organizations/{id}/auth-clients`.
 *
 * `default_scope` MUST be one of the entries in `allowed_scopes`;
 * the backend validates this and the create dialog mirrors the rule
 * client-side so the user gets immediate feedback.
 */
export interface AuthClientCreateRequest {
  client_id: string;
  name?: string;
  expected_subject_azp: string;
  expected_subject_audience?: string;
  allowed_scopes: string[];
  default_scope: string;
}
