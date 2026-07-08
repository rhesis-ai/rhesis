/**
 * Extension points for member role display and assignment.
 *
 * Core grids (TeamMembersGrid, ProjectMembers) and drawers
 * (ProjectAddMemberDrawer) use these slots to render role chips and
 * role pickers when RBAC is available. Without registration the grids
 * fall back to their community behaviour (no role column or a static
 * "member" label).
 *
 * EE registers implementations from `ee/frontend/src/rbac/register.tsx`.
 */

import type { ComponentType } from 'react';

// ---------------------------------------------------------------------------
// Prop contracts for the extension slots
// ---------------------------------------------------------------------------

export interface OrgRoleCellProps {
  userId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
  /** The signed-in viewer's user id. When it matches `userId`, the cell
   *  should render read-only — changing your own org role is high-risk
   *  (self-demotion) and gets no confirmation loop, so it is disabled
   *  rather than merely discouraged. */
  currentUserId?: string;
}

export interface ProjectRoleCellProps {
  userId: string;
  projectId: string;
  sessionToken: string;
  onRoleChanged?: () => void;
}

export interface AddMemberRoleFieldProps {
  sessionToken: string;
  value: string | null;
  onChange: (roleId: string | null) => void;
  /** 'small' renders a compact inline Select without a label, suitable for
   *  use inside list items. Defaults to 'medium' (full FormControl). */
  size?: 'small' | 'medium';
}

/** Minimal project fields returned by the bulk project-memberships endpoint. */
export interface ProjectSummary {
  id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
}

/** A user's membership in a single project, returned by the bulk endpoint. */
export interface UserProjectMembership {
  project_id: string;
  user_id: string;
  role_id: string | null;
  role?: { display_name: string } | null;
  project: ProjectSummary;
}

// ---------------------------------------------------------------------------
// Extension bundle
// ---------------------------------------------------------------------------

export interface MemberRoleExtensions {
  /** Renders an org-level role chip in the team members grid. */
  OrgRoleCell?: ComponentType<OrgRoleCellProps>;
  /** Renders a project-level role chip in the project members grid. */
  ProjectRoleCell?: ComponentType<ProjectRoleCellProps>;
  /** Renders a role picker in the add-member drawer. */
  AddMemberRoleField?: ComponentType<AddMemberRoleFieldProps>;
  /** Assigns a project role after a member is added via the community endpoint. */
  assignProjectMemberRole?: (
    sessionToken: string,
    projectId: string,
    userId: string,
    roleId: string
  ) => Promise<void>;
  /** Fetches all project memberships for a user in a single call (EE bulk endpoint). */
  fetchUserProjectMemberships?: (
    sessionToken: string,
    userId: string
  ) => Promise<UserProjectMembership[]>;
  /**
   * Pre-warm RBAC caches so chips render immediately instead of each row
   * triggering its own fetch. Org members are always fetched (every role
   * chip needs them). Roles are gated on `canManageRoles` — `GET /rbac/roles`
   * requires `Permission.Role.READ`, which viewers without member-management
   * rights don't hold, so fetching it unconditionally would fire a doomed
   * 403 for every non-admin page load.
   */
  prewarmCaches?: (
    sessionToken: string,
    opts?: { canManageRoles?: boolean }
  ) => void;
  /**
   * Pre-warm RBAC caches for a single project's members grid, so
   * `ProjectRoleCell` renders immediately instead of each row triggering its
   * own fetch after the community members query resolves. Same
   * `canManageRoles` gate as `prewarmCaches` — `GET /rbac/roles` requires
   * `Permission.Role.READ`.
   */
  prewarmProjectCaches?: (
    sessionToken: string,
    projectId: string,
    opts?: { canManageRoles?: boolean }
  ) => void;
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

let _extensions: MemberRoleExtensions = {};

export function registerMemberRoleExtensions(ext: MemberRoleExtensions): void {
  _extensions = { ..._extensions, ...ext };
}

export function getMemberRoleExtensions(): Readonly<MemberRoleExtensions> {
  return _extensions;
}

export function resetMemberRoleExtensions(): void {
  _extensions = {};
}
