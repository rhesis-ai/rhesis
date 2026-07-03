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
   *  in migration a2b3c4d5e6f7; custom roles default to "". */
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

export interface OrgMemberRead {
  id: string;
  organization_id: string;
  user_id: string;
  role_id: string;
  role?: RoleRead;
}

export interface OrgRoleAssign {
  role_id: string;
}

export interface ProjectMemberRoleRead {
  project_id: string;
  user_id: string;
  role_id: string;
  role?: RoleRead;
}

export interface ProjectMemberRoleAssign {
  role_id: string;
}
