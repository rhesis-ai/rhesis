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
  data: OrgMemberRead[];
  ts: number;
}

let _cache: CacheEntry | null = null;
let _pending: Promise<OrgMemberRead[]> | null = null;

const TTL_MS = 30_000;

export function fetchOrgMembers(): Promise<OrgMemberRead[]> {
  // Not keyed by account: an account change always goes through a full-page
  // logout redirect that tears down this module's state, and the 30s TTL
  // bounds any residual staleness. (Requests authenticate via the BFF proxy's
  // httpOnly cookie — no token is available client-side to key by.)
  if (_cache && Date.now() - _cache.ts < TTL_MS) {
    return Promise.resolve(_cache.data);
  }
  if (_pending) return _pending;

  const promise = new RbacClient()
    .getOrganizationMembers()
    .then(data => {
      _cache = { data, ts: Date.now() };
      _pending = null;
      return data;
    })
    .catch(err => {
      _pending = null;
      throw err;
    });
  _pending = promise;
  return promise;
}

export function invalidateOrgMembers(): void {
  _cache = null;
}

export function getCachedOrgMembers(): OrgMemberRead[] {
  return _cache?.data ?? [];
}
