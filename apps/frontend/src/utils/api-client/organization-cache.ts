/**
 * Module-level organization cache shared by all client components.
 *
 * The current user's organization is identical for every component that needs
 * it, so fetching it once per page load is sufficient. Independent callers
 * (e.g. the models page and the org settings page) — and React Strict Mode's
 * double-invoked effects in development — would otherwise each issue their own
 * `GET /organizations/{id}` (plus a CORS preflight). This mirrors the
 * deduplication pattern in `ee/frontend/src/rbac/api/role-cache.ts`: a short-
 * lived cache plus an in-flight promise that collapses concurrent requests
 * into a single network call.
 */

import { ApiClientFactory } from './client-factory';
import { Organization } from './interfaces/organization';

interface CacheEntry {
  key: string;
  data: Organization;
  ts: number;
}

let _cache: CacheEntry | null = null;
let _pending: Promise<Organization> | null = null;
let _pendingKey: string | null = null;

const CACHE_TTL_MS = 30_000;

function cacheKey(sessionToken: string, organizationId: string): string {
  return `${sessionToken}::${organizationId}`;
}

/**
 * Fetch the organization, deduplicating concurrent and repeated calls.
 *
 * Concurrent callers share the same in-flight promise; subsequent callers
 * within the TTL receive the cached value without a network round-trip. After
 * mutating the organization, call {@link invalidateOrganization} so the next
 * fetch reloads fresh data.
 */
export function fetchOrganization(
  sessionToken: string,
  organizationId: string
): Promise<Organization> {
  const key = cacheKey(sessionToken, organizationId);

  if (_cache && _cache.key === key && Date.now() - _cache.ts < CACHE_TTL_MS) {
    return Promise.resolve(_cache.data);
  }
  if (_pending && _pendingKey === key) {
    return _pending;
  }

  const promise = new ApiClientFactory(sessionToken)
    .getOrganizationsClient()
    .getOrganization(organizationId)
    .then(data => {
      _cache = { key, data, ts: Date.now() };
      if (_pendingKey === key) {
        _pending = null;
        _pendingKey = null;
      }
      return data;
    })
    .catch(err => {
      if (_pendingKey === key) {
        _pending = null;
        _pendingKey = null;
      }
      throw err;
    });

  _pending = promise;
  _pendingKey = key;
  return promise;
}

/**
 * Drop the cached organization. Call after any mutation (e.g. updating org
 * details) so the next {@link fetchOrganization} reflects the change.
 */
export function invalidateOrganization(): void {
  _cache = null;
}
