/**
 * Status of the deployment-wide Rhesis platform API key.
 *
 * Only meaningful on a local/self-hosted deployment, where the prepopulated
 * Rhesis-hosted models (Rhesis Default, Rhesis Default Embedding, Rhesis
 * Polyphemus) require a Rhesis platform API key to function. Shape mirrors the
 * backend `GET/PUT /platform/rhesis-key` response.
 */
export interface PlatformKeyStatus {
  /** Whether a platform key is currently stored. */
  configured: boolean;
  /** Whether the stored key validated against the Rhesis platform, or null if unchecked. */
  valid: boolean | null;
  /** Whether the stored key is authorized for Polyphemus, or null if unchecked. */
  polyphemus_authorized: boolean | null;
  /** Masked representation of the stored key (e.g. `rh_...abcd`), or null when unset. */
  masked_key: string | null;
  /** ISO timestamp of the last validation check, or null when never checked. */
  last_checked_at: string | null;
}

/** Response shape for a successful `DELETE /platform/rhesis-key`. */
export interface PlatformKeyCleared {
  configured: false;
}
