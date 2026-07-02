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
  scope: string;
  /** Internal ordering — higher = more privileged. Never display to users. */
  level: number;
  is_built_in: boolean;
  organization_id: string | null;
  permissions: PermissionRead[];
}

export interface RoleCreate {
  name: string;
  display_name?: string;
  scope?: string;
  permission_names: string[];
}

export interface RoleUpdate {
  display_name?: string;
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
