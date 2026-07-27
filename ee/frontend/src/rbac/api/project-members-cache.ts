/**
 * Module-level per-project cache for project members.
 *
 * Shared between ProjectRoleChip and useActorAuthority so a project's member
 * list is fetched once per render cycle rather than once per consumer. Mirrors
 * the singleton pattern in `org-members-cache.ts` and `role-cache.ts`.
 */

import { RbacClient } from './rbac-client';
import type { ProjectMemberRoleRead } from '../types';

interface CacheEntry {
  data: ProjectMemberRoleRead[];
  ts: number;
}

const _cache = new Map<string, CacheEntry>();
const _pending = new Map<string, Promise<ProjectMemberRoleRead[]>>();

const TTL_MS = 30_000;

// Keyed by projectId alone. Not keyed by account: an account change always
// goes through a full-page logout redirect that tears down this module's
// state, and the 30s TTL bounds any residual staleness. (Requests
// authenticate via the BFF proxy's httpOnly cookie — no token is available
// client-side to key by.)
export function fetchProjectMembers(
  projectId: string
): Promise<ProjectMemberRoleRead[]> {
  const key = projectId;
  const cached = _cache.get(key);
  if (cached && Date.now() - cached.ts < TTL_MS) {
    return Promise.resolve(cached.data);
  }
  const pending = _pending.get(key);
  if (pending) return pending;

  const promise = new RbacClient()
    .getProjectMembers(projectId)
    .then(data => {
      _cache.set(key, { data, ts: Date.now() });
      _pending.delete(key);
      return data;
    })
    .catch(err => {
      _pending.delete(key);
      throw err;
    });
  _pending.set(key, promise);
  return promise;
}

export function invalidateProjectMembers(projectId: string): void {
  _cache.delete(projectId);
}

export function hasProjectMembers(projectId: string): boolean {
  return _cache.has(projectId);
}

export function getCachedProjectMembers(
  projectId: string
): ProjectMemberRoleRead[] {
  return _cache.get(projectId)?.data ?? [];
}
