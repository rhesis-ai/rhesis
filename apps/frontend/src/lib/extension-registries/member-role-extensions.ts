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
