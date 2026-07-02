"use client";

/**
 * useActorAuthority — resolves the current user's effective privilege level
 * and permission set.
 *
 * Both values drive the frontend privilege-escalation guard, mirroring the
 * two-part `_check_escalation` in `ee/backend/.../rbac/router.py`:
 *   1. role_level  > actor_level        → deny
 *   2. role.perms ⊄ actor.perms        → deny  (custom roles only)
 *
 * Resolution order (matches `PermissionAuthorizationProvider._resolve_role`):
 *   org tier     → org membership role.
 *   project tier → explicit project role, fallback to org role when the user
 *                  has implicit access (org Owner/Admin, no project_membership row).
 *
 * Returns { level: 0, permissionNames: empty set } while data is loading or
 * when the actor has no role.  Callers treat that as "no assignable roles" —
 * the backend enforces the same guard on every write.
 */

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { fetchOrgMembers } from "../api/org-members-cache";
import { fetchProjectMembers } from "../api/project-members-cache";
import { fetchRoles } from "../api/role-cache";
import type { RoleRead } from "../types";

export interface ActorAuthority {
  level: number;
  /** Full set of permission names the actor holds at this tier. */
  permissionNames: ReadonlySet<string>;
}

const EMPTY: ActorAuthority = { level: 0, permissionNames: new Set() };

function authorityFromRole(role: RoleRead | undefined): ActorAuthority {
  if (!role) return EMPTY;
  return {
    level: role.level,
    permissionNames: new Set(role.permissions.map((p) => p.name)),
  };
}

export function useActorAuthority(
  sessionToken: string,
  tier: "org",
): ActorAuthority;

export function useActorAuthority(
  sessionToken: string,
  tier: "project",
  projectId: string,
): ActorAuthority;

export function useActorAuthority(
  sessionToken: string,
  tier: "org" | "project",
  projectId?: string,
): ActorAuthority {
  const { data: session } = useSession();
  const myUserId = (session?.user as { id?: string } | undefined)?.id;

  const [authority, setAuthority] = useState<ActorAuthority>(EMPTY);

  useEffect(() => {
    if (!sessionToken || !myUserId) return;
    let cancelled = false;

    async function resolve() {
      const [orgMembers, roles] = await Promise.all([
        fetchOrgMembers(sessionToken),
        fetchRoles(sessionToken),
      ]);

      const findRole = (roleId: string | null | undefined): RoleRead | undefined =>
        roleId ? roles.find((r) => r.id === roleId) : undefined;

      const myOrgMember = orgMembers.find((m) => m.user_id === myUserId);
      const orgAuthority = authorityFromRole(findRole(myOrgMember?.role_id));

      // Org tier, or project tier with no project resolved yet: use org role.
      if (tier === "org" || !projectId) {
        if (!cancelled) setAuthority(orgAuthority);
        return;
      }

      const projectMembers = await fetchProjectMembers(sessionToken, projectId);
      const myProjectMember = projectMembers.find((m) => m.user_id === myUserId);

      // Explicit project role takes precedence; otherwise fall back to the org
      // role (implicit access for Owner/Admin — the access policy itself is
      // enforced server-side).
      const effective = myProjectMember?.role_id
        ? authorityFromRole(findRole(myProjectMember.role_id))
        : orgAuthority;

      if (!cancelled) setAuthority(effective);
    }

    resolve().catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [sessionToken, myUserId, tier, projectId]);

  return authority;
}
