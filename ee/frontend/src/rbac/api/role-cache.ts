/**
 * Module-level role catalog cache shared by all RBAC components.
 *
 * The roles list is org-wide and identical for every grid row, so fetching
 * it once per page load is sufficient. This mirrors the same deduplication
 * pattern used for `fetchOrgMembers` in OrgRoleChip and `fetchProjectMembers`
 * in ProjectRoleChip, preventing an N-requests-per-row storm when role chips
 * are rendered in a data grid.
 */

import { RbacClient } from './rbac-client';
import type { RoleRead } from '../types';

interface CacheEntry {
  key: string;
  data: RoleRead[];
  ts: number;
}

let _rolesCache: CacheEntry | null = null;
let _rolesPending: Promise<RoleRead[]> | null = null;

const CACHE_TTL_MS = 30_000;

export interface FetchRolesOptions {
  /** Skip the in-memory cache and fetch a fresh catalog from the API. */
  bypassCache?: boolean;
}

export function fetchRoles(
  sessionToken: string,
  options?: FetchRolesOptions
): Promise<RoleRead[]> {
  const bypassCache = options?.bypassCache ?? false;

  if (
    !bypassCache &&
    _rolesCache &&
    _rolesCache.key === sessionToken &&
    Date.now() - _rolesCache.ts < CACHE_TTL_MS
  ) {
    return Promise.resolve(_rolesCache.data);
  }
  if (!bypassCache && _rolesPending) return _rolesPending;

  const fetchPromise = new RbacClient(sessionToken)
    .getRoles()
    .then(data => {
      _rolesCache = { key: sessionToken, data, ts: Date.now() };
      _rolesPending = null;
      return data;
    })
    .catch(err => {
      _rolesPending = null;
      throw err;
    });

  if (!bypassCache) {
    _rolesPending = fetchPromise;
  }

  return fetchPromise;
}

export function invalidateRoles(): void {
  _rolesCache = null;
  _rolesPending = null;
}
