import { serverFetch } from '../server-fetch';
import type { TermsStatus } from './auth-client';

/**
 * Server-side fetch of `GET /auth/terms-status`. Called once from the
 * `(protected)` layout so `TermsAcceptanceGate` can render its decision on
 * first paint without a client-side round trip.
 *
 * Returns `null` on any failure — the client falls back to its own fetch.
 */
export async function fetchTermsStatusServer(
  accessToken: string
): Promise<TermsStatus | null> {
  try {
    const response = await serverFetch('/auth/terms-status', { accessToken });
    if (!response.ok) return null;
    const data = await response.json();
    return {
      terms_accepted: Boolean(data.terms_accepted),
      has_prior_acceptance: Boolean(data.has_prior_acceptance),
    };
  } catch {
    return null;
  }
}
