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

// Keyed by sessionToken:projectId so a session/account change never reuses a
// prior user's member/role data for the same project.
function cacheKey(sessionToken: string, projectId: string): string {
  return `${sessionToken}:${projectId}`;
}

export function fetchProjectMembers(
  sessionToken: string,
  projectId: string
): Promise<ProjectMemberRoleRead[]> {
  const key = cacheKey(sessionToken, projectId);
  const cached = _cache.get(key);
  if (cached && Date.now() - cached.ts < TTL_MS) {
    return Promise.resolve(cached.data);
  }
  const pending = _pending.get(key);
  if (pending) return pending;

  const promise = new RbacClient(sessionToken)
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

export function invalidateProjectMembers(
  sessionToken: string,
  projectId: string
): void {
  _cache.delete(cacheKey(sessionToken, projectId));
}

export function hasProjectMembers(
  sessionToken: string,
  projectId: string
): boolean {
  return _cache.has(cacheKey(sessionToken, projectId));
}

export function getCachedProjectMembers(
  sessionToken: string,
  projectId: string
): ProjectMemberRoleRead[] {
  return _cache.get(cacheKey(sessionToken, projectId))?.data ?? [];
}
