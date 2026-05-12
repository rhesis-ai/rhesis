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
}

export interface SSOTestResult {
  success: boolean;
  message: string;
}
