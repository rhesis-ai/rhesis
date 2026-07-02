/**
 * Module-level singleton cache for org members.
 *
 * Shared between OrgRoleChip and ProjectRoleChip so that only one fetch fires
 * per render cycle and both chips can resolve the current user's org-level role
 * (needed as a fallback when the user has implicit project access and is not in
 * the project members list).
 */

import { RbacClient } from "./rbac-client";
import type { OrgMemberRead } from "../types";

interface CacheEntry {
  key: string;
  data: OrgMemberRead[];
  ts: number;
}

let _cache: CacheEntry | null = null;
let _pending: Promise<OrgMemberRead[]> | null = null;

const TTL_MS = 30_000;

export function fetchOrgMembers(sessionToken: string): Promise<OrgMemberRead[]> {
  if (_cache && _cache.key === sessionToken && Date.now() - _cache.ts < TTL_MS) {
    return Promise.resolve(_cache.data);
  }
  if (_pending) return _pending;

  _pending = new RbacClient(sessionToken)
    .getOrganizationMembers()
    .then((data) => {
      _cache = { key: sessionToken, data, ts: Date.now() };
      _pending = null;
      return data;
    })
    .catch((err) => {
      _pending = null;
      throw err;
    });
  return _pending;
}

export function invalidateOrgMembers(): void {
  _cache = null;
}

export function getCachedOrgMembers(): OrgMemberRead[] {
  return _cache?.data ?? [];
}
