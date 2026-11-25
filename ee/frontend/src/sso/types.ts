/**
 * SSO-specific shapes.
 *
 * Lives in EE rather than core because the JSON shape of `sso_config`
 * is owned by the SSO feature, not by the platform. Core's
 * `Organization` interface treats `sso_config` as `unknown`; consumers
 * inside EE narrow it via these types.
 */

export interface SSOConfig {
  enabled: boolean;
  provider_type: string;
  issuer_url: string;
  client_id: string;
  client_secret?: string;
  scopes: string;
  auto_provision_users: boolean;
  allowed_domains?: string[] | null;
  allowed_auth_methods?: string[] | null;
  allow_insecure_tls: boolean;
  slug?: string;
  login_url?: string;
  /** A provider key from the backend catalog; only changes wording and hints. */
  provider?: string;
  role_mapping?: RoleMapping | null;
}

/** One entry of the backend's provider catalog (`GET .../sso/providers`). */
export interface ProviderInfo {
  key: string;
  /** Short name used in sentences ("your Okta groups"). */
  name: string;
  title: string;
  /** False when the provider never puts groups in the sign-in token. */
  supports_groups: boolean;
  /** How to get a groups claim into the token. */
  groups_hint: string;
}

/** A claim name, or path segments for a nested claim (`["realm_access", "roles"]`). */
export type ClaimPath = string | string[];

export interface ProjectGrant {
  project_id: string;
  role_id: string;
}

export interface MappingRule {
  /** Exactly what the token carries: a name, a path or an ID. */
  group: string;
  role_id: string | null;
  projects: ProjectGrant[];
}

export type EveryoneElse = 'keep' | 'Viewer' | 'None' | 'block';
export type ApplyMode = 'every_sign_in' | 'on_create';

export interface RoleMapping {
  enabled: boolean;
  claim: ClaimPath;
  apply: ApplyMode;
  rules: MappingRule[];
  everyone_else: EveryoneElse;
}

export interface SeenGroup {
  value: string;
  members: number;
}

export interface SeenClaims {
  groups: SeenGroup[];
  /** Every claim path seen with a list of strings. */
  claims: string[][];
}

export interface RoleChange {
  user_id: string;
  name: string;
  email: string;
  from_role: string | null;
  to_role: string | null;
  blocked: boolean;
  less_access: boolean;
}

export interface RoleMappingPreview {
  changes: RoleChange[];
  /** Members with no SSO sign-in since role mapping shipped. */
  without_sign_in: number;
  /** The mapping runs only at a first SSO sign-in, so existing members keep their roles. */
  new_accounts_only: boolean;
}

export interface SSOTestResult {
  success: boolean;
  message: string;
  provider?: string | null;
}
