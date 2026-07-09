/**
 * Module-level singleton cache for org members.
 *
 * Shared between OrgRoleChip and ProjectRoleChip so that only one fetch fires
 * per render cycle and both chips can resolve the current user's org-level role
 * (needed as a fallback when the user has implicit project access and is not in
 * the project members list).
 */

import { RbacClient } from './rbac-client';
import type { OrgMemberRead } from '../types';

interface CacheEntry {
  key: string;
  data: OrgMemberRead[];
  ts: number;
}

let _cache: CacheEntry | null = null;
let _pending: { key: string; promise: Promise<OrgMemberRead[]> } | null = null;

const TTL_MS = 30_000;

export function fetchOrgMembers(
  sessionToken: string
): Promise<OrgMemberRead[]> {
  if (
    _cache &&
    _cache.key === sessionToken &&
    Date.now() - _cache.ts < TTL_MS
  ) {
    return Promise.resolve(_cache.data);
  }
  // Keyed by sessionToken so an in-flight fetch for a prior session/account
  // is never handed back to a caller running under a new one.
  if (_pending && _pending.key === sessionToken) return _pending.promise;

  const promise = new RbacClient(sessionToken)
    .getOrganizationMembers()
    .then(data => {
      _cache = { key: sessionToken, data, ts: Date.now() };
      _pending = null;
      return data;
    })
    .catch(err => {
      _pending = null;
      throw err;
    });
  _pending = { key: sessionToken, promise };
  return promise;
}

export function invalidateOrgMembers(): void {
  _cache = null;
}

export function getCachedOrgMembers(): OrgMemberRead[] {
  return _cache?.data ?? [];
}
