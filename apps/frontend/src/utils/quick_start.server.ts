import { serverFetch } from './server-fetch';

interface AuthConfigResponse {
  quick_start?: boolean;
}

/**
 * Server-side fetch of the Quick Start flag from `GET /auth/providers`.
 * Called once from the root layout so the result can be threaded down via
 * `QuickStartProvider`, eliminating duplicate client-side `/api/auth-config`
 * calls that previously fired on every page load.
 *
 * Unauthenticated — no token needed.
 */
export async function fetchQuickStartEnabledServer(): Promise<boolean> {
  try {
    const response = await serverFetch('/auth/providers');
    if (!response.ok) return false;
    const data = (await response.json()) as AuthConfigResponse;
    return data.quick_start === true;
  } catch {
    return false;
  }
}
