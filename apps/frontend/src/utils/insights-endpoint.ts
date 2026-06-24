export const INSIGHTS_ENDPOINT_COOKIE = 'rh_insights_endpoint_id';

/** Read the insights endpoint ID from the cookie (client-side only). */
export function readInsightsEndpointId(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split('; ')
    .find(row => row.startsWith(`${INSIGHTS_ENDPOINT_COOKIE}=`));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

/** Persist the insights endpoint ID in the cookie. */
export function writeInsightsEndpointId(id: string): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${INSIGHTS_ENDPOINT_COOKIE}=${encodeURIComponent(id)}; path=/; SameSite=Lax; max-age=${60 * 60 * 24 * 365}`;
}

/** Clear the insights endpoint cookie. */
export function clearInsightsEndpointId(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${INSIGHTS_ENDPOINT_COOKIE}=; path=/; SameSite=Lax; max-age=0`;
}
