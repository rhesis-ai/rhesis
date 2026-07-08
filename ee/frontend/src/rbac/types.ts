/**
 * RBAC type definitions mirroring backend Pydantic schemas.
 *
 * Source of truth: `ee/backend/src/rhesis/backend/ee/rbac/schemas.py`.
 * Keep in sync when the backend adds fields.
 */

export interface PermissionRead {
  id: string;
  name: string;
  display_name: string;
  resource_type: string;
  action: string;
  scope: string;
  is_retired: boolean;
}

export interface RoleRead {
  id: string;
  name: string;
  display_name: string;
  /** One-sentence description served by the backend. Built-in roles are seeded
   *  in migration 671d10bef526; custom roles default to "". */
  description: string;
  scope: string;
  /** Privilege ordering — higher = more privileged. Drive sorting and filter
   *  logic off this field; never branch on `name` strings. */
  level: number;
  is_built_in: boolean;
  organization_id: string | null;
  permissions: PermissionRead[];
  /** Distinct users holding this role, across org + project assignments. */
  member_count: number;
}

export interface RoleCreate {
  name: string;
  display_name?: string;
  description?: string;
  scope?: string;
  permission_names: string[];
}

export interface RoleUpdate {
  display_name?: string;
  description?: string;
  permission_names?: string[];
}

export interface UserSummary {
  id: string;
  name?: string | null;
  given_name?: string | null;
  family_name?: string | null;
  email: string;
  picture?: string | null;
  auth0_id?: string | null;
}

export interface OrgMemberRead {
  id: string;
  organization_id: string;
  user_id: string;
  role_id: string;
  role?: RoleRead;
  user?: UserSummary | null;
  /** Capability strings the caller may exercise on THIS member (e.g.
   *  "member:manage", "member:delete"), server-resolved. Encodes the
   *  privilege-escalation guard (self-change and outranking are both
   *  denied) — check with `can()`, never re-derive it client-side. */
  permitted_actions?: string[];
}

export interface OrgRoleAssign {
  role_id: string;
}

export interface ProjectMemberRoleRead {
  project_id: string;
  user_id: string;
  role_id: string | null;
  role?: RoleRead | null;
  /** Capability strings the caller may exercise on THIS member (e.g.
   *  "member:manage"), server-resolved. Encodes the privilege-escalation
   *  guard (self-change and outranking are both denied) — check with
   *  `can()`, never re-derive it client-side. */
  permitted_actions?: string[];
}

export interface ProjectMemberRoleAssign {
  role_id: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description?: string | null;
  icon?: string | null;
}

export interface UserProjectMembershipRead {
  project_id: string;
  user_id: string;
  role_id: string | null;
  role?: RoleRead | null;
  project: ProjectSummary;
}
