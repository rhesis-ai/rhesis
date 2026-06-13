export const ACTIVE_PROJECT_COOKIE = 'rh_active_project_id';

/** Read the active project ID from the cookie (client-side only). */
export function readActiveProjectId(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie
    .split('; ')
    .find(row => row.startsWith(`${ACTIVE_PROJECT_COOKIE}=`));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

/** Persist the active project ID in the cookie. */
export function writeActiveProjectId(id: string): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${ACTIVE_PROJECT_COOKIE}=${encodeURIComponent(id)}; path=/; SameSite=Lax; max-age=${60 * 60 * 24 * 365}`;
}

/** Clear the active project cookie. */
export function clearActiveProjectId(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${ACTIVE_PROJECT_COOKIE}=; path=/; SameSite=Lax; max-age=0`;
}
