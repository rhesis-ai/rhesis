/**
 * Module-level per-project cache for project members.
 *
 * Shared between ProjectRoleChip and useActorAuthority so a project's member
 * list is fetched once per render cycle rather than once per consumer. Mirrors
 * the singleton pattern in `org-members-cache.ts` and `role-cache.ts`.
 */

import { RbacClient } from "./rbac-client";
import type { ProjectMemberRoleRead } from "../types";

interface CacheEntry {
  data: ProjectMemberRoleRead[];
  ts: number;
}

const _cache = new Map<string, CacheEntry>();
const _pending = new Map<string, Promise<ProjectMemberRoleRead[]>>();

const TTL_MS = 30_000;

export function fetchProjectMembers(
  sessionToken: string,
  projectId: string,
): Promise<ProjectMemberRoleRead[]> {
  const cached = _cache.get(projectId);
  if (cached && Date.now() - cached.ts < TTL_MS) {
    return Promise.resolve(cached.data);
  }
  const pending = _pending.get(projectId);
  if (pending) return pending;

  const promise = new RbacClient(sessionToken)
    .getProjectMembers(projectId)
    .then((data) => {
      _cache.set(projectId, { data, ts: Date.now() });
      _pending.delete(projectId);
      return data;
    })
    .catch((err) => {
      _pending.delete(projectId);
      throw err;
    });
  _pending.set(projectId, promise);
  return promise;
}

export function invalidateProjectMembers(projectId: string): void {
  _cache.delete(projectId);
}

export function hasProjectMembers(projectId: string): boolean {
  return _cache.has(projectId);
}

export function getCachedProjectMembers(
  projectId: string,
): ProjectMemberRoleRead[] {
  return _cache.get(projectId)?.data ?? [];
}
