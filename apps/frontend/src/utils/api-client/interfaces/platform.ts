/**
 * Status of the deployment-wide Rhesis platform API key.
 *
 * Only meaningful on a local/self-hosted deployment, where the prepopulated
 * Rhesis-hosted models (Rhesis, Rhesis Embedding, Rhesis
 * Polyphemus) require a Rhesis platform API key to function. Shape mirrors the
 * backend `GET/PUT/DELETE /platform/rhesis-key` response.
 */
export interface PlatformKeyStatus {
  /** Whether a platform key is currently stored. */
  configured: boolean;
  /**
   * Where the effective key comes from. Only an `organization` key can be
   * removed; an `environment` key lives in the deployment's `RHESIS_API_KEY`
   * and can only be overridden by saving an org key.
   */
  source: 'organization' | 'environment' | null;
  /** Whether the stored key validated against the Rhesis platform, or null if unchecked. */
  valid: boolean | null;
  /** Whether the stored key is authorized for Polyphemus, or null if unchecked. */
  polyphemus_authorized: boolean | null;
  /** Masked representation of the stored key (e.g. `rh_...abcd`), or null when unset. */
  masked_key: string | null;
  /** ISO timestamp of the last validation check, or null when never checked. */
  last_checked_at: string | null;
}
