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

export function fetchRoles(sessionToken: string): Promise<RoleRead[]> {
  if (
    _rolesCache &&
    _rolesCache.key === sessionToken &&
    Date.now() - _rolesCache.ts < CACHE_TTL_MS
  ) {
    return Promise.resolve(_rolesCache.data);
  }
  if (_rolesPending) return _rolesPending;

  _rolesPending = new RbacClient(sessionToken)
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
  return _rolesPending;
}

export function invalidateRoles(): void {
  _rolesCache = null;
}
