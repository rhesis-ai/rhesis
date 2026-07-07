/**
 * Frontend display utilities for RBAC roles.
 *
 * All logic is keyed off the numeric `level` field that the backend already
 * returns on every `RoleRead`.  No role-name strings live here — that was the
 * source of the previous case-mismatch bugs.
 *
 * Level reference (from BUILT_IN_ROLE_LEVELS in ee/backend/rbac/models.py):
 *   Owner  = 100  (highest privilege — not assignable to others)
 *   Admin  = 80
 *   Member = 60
 *   Viewer = 40
 *   None   = 0   (zero privilege — explicit revocation, not a useful assignment)
 *
 * Custom roles use level 50 by default (below Member).
 */

import { alpha } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import type { RoleRead } from './types';

/**
 * Returns MUI `sx`-compatible styles for a role chip.
 *
 * Built-in roles are styled by level bracket; custom roles get a consistent
 * "warning" amber style.  The returned object may contain theme-function
 * values (`(t: Theme) => ...`) accepted by MUI's `sx` prop.
 */
/**
 * MUI Chip renders its text inside an inner `.MuiChip-label` span whose color
 * is set by the component's own style sheet.  Setting `color` at the root
 * level is not specific enough to win; we must target the label slot directly.
 */
function chipSx(
  bg: string | ((t: Theme) => string),
  fg: string | ((t: Theme) => string),
  extra: Record<string, unknown> = {}
): Record<string, unknown> {
  return {
    bgcolor: bg,
    color: fg,
    '& .MuiChip-label': { color: fg },
    ...extra,
  };
}

export function getRoleChipSx(role: RoleRead): Record<string, unknown> {
  if (!role.is_built_in) {
    return chipSx(
      (t: Theme) => alpha(t.palette.warning.main, 0.1),
      'warning.dark',
      { fontWeight: 600 }
    );
  }

  // Owner (level 100)
  if (role.level >= 100) {
    return chipSx('primary.main', 'primary.contrastText', { fontWeight: 600 });
  }
  // Admin (level 80)
  if (role.level >= 80) {
    return chipSx(
      (t: Theme) => alpha(t.palette.primary.light, 0.13),
      'primary.dark',
      { fontWeight: 600 }
    );
  }
  // Member (level 60)
  if (role.level >= 60) {
    return chipSx(
      (t: Theme) => alpha(t.palette.primary.light, 0.08),
      'primary.main'
    );
  }
  // Viewer (level 40)
  if (role.level > 0) {
    return chipSx(
      (t: Theme) => t.palette.greyscale.surface2,
      (t: Theme) => t.palette.greyscale.label
    );
  }
  // None (level 0) — outlined / no fill
  return {
    ...chipSx('transparent', (t: Theme) => t.palette.greyscale.subtitle),
    border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
  };
}

/**
 * Whether a role can be assigned to a user at the **org** tier.
 *
 * None (level 0) is excluded — explicit revocation is not a useful assignment.
 * Owner (level 100) is permitted: the backend allows multiple org owners and
 * only protects against removing the *last* one.
 */
export function isAssignableOrgRole(role: RoleRead): boolean {
  return !role.is_built_in || role.level > 0;
}

/**
 * Whether a role can be assigned to a user at the **project** tier.
 *
 * Only None (level 0) is excluded — it means "no access" (explicit revocation)
 * and is not a useful assignment.  Owner (level 100) IS allowed at the project
 * tier so that a project creator or lead can be designated as the project owner,
 * independent of who holds the org-level Owner role.
 */
export function isAssignableProjectRole(role: RoleRead): boolean {
  return !role.is_built_in || role.level > 0;
}

/**
 * Whether a role is within the actor's authority to assign.
 *
 * Mirrors the two-part backend `_check_escalation`:
 *   1. Level gate  — role.level must be ≤ actor level.
 *   2. Permission gate (custom roles only) — every permission on the role must
 *      be held by the actor.  Built-in roles are exempt because their effective
 *      permission set is computed server-side and is always a strict subset of a
 *      higher-level built-in role (the level gate is sufficient).
 */
export function isWithinActorAuthority(
  role: RoleRead,
  actorLevel: number,
  actorPermissions: ReadonlySet<string>
): boolean {
  if (role.level > actorLevel) return false;
  if (!role.is_built_in) {
    return role.permissions.every(p => actorPermissions.has(p.name));
  }
  return true;
}

/**
 * Whether a role may be used as a "copy permissions from" template when
 * creating a custom role.
 *
 * Excludes Owner (too broad to copy wholesale) and None (no permissions).
 */
export function isCopyableRole(role: RoleRead): boolean {
  return role.is_built_in && role.level > 0 && role.level < 100;
}
