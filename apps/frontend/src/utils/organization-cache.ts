import type { Organization } from '@/utils/api-client/interfaces/organization';

/**
 * Server-side, cross-request cache of the caller's organisation.
 *
 * The root layout's `generateMetadata` reads the organisation for branding, and
 * Next runs it again for every sidebar link prefetch, so one page view used to
 * fetch `/organizations/{id}` seven or eight times. React `cache()` only dedupes
 * within one render.
 *
 * Entries are per user, because the response carries the caller's
 * `permitted_actions`. They live for {@link TTL_MS}, like the backend's own
 * permission cache, and `forgetOrganization` drops them when the BFF forwards a
 * write to the organisation, so a settings change shows on the next render
 * served by the same instance and on other instances within the TTL.
 */
const TTL_MS = 30_000;
const MAX_ENTRIES = 1000;

interface Entry {
  value: Organization;
  expiresAt: number;
}

// On globalThis so the layout and the BFF route handler share one map even when
// Next bundles them separately.
const globalStore = globalThis as typeof globalThis & {
  __rhesisOrganizationCache?: Map<string, Entry>;
};
const entries = (globalStore.__rhesisOrganizationCache ??= new Map());

const keyOf = (userId: string, organizationId: string) =>
  `${organizationId}:${userId}`;

export async function cachedOrganization(
  userId: string,
  organizationId: string,
  load: () => Promise<Organization>
): Promise<Organization> {
  const key = keyOf(userId, organizationId);
  const hit = entries.get(key);
  if (hit && hit.expiresAt > Date.now()) return hit.value;

  const value = await load();
  entries.delete(key);
  entries.set(key, { value, expiresAt: Date.now() + TTL_MS });
  if (entries.size > MAX_ENTRIES) {
    // Maps iterate in insertion order, so the first key is the oldest write.
    entries.delete(entries.keys().next().value as string);
  }
  return value;
}

/** Drop every user's cached copy of an organisation. */
export function forgetOrganization(organizationId: string): void {
  const prefix = `${organizationId}:`;
  for (const key of entries.keys()) {
    if (key.startsWith(prefix)) entries.delete(key);
  }
}

const ORGANIZATION_PATH = /^\/organizations\/([^/]+)/;

/** The organisation a backend path writes to, if any. */
export function organizationWrittenBy(
  method: string,
  backendPath: string
): string | null {
  if (method === 'GET' || method === 'HEAD') return null;
  return ORGANIZATION_PATH.exec(backendPath)?.[1] ?? null;
}
