/**
 * RBAC API client.
 *
 * Owns all calls to the `/rbac/` EE endpoints. Mirrors the shape of
 * `SSOClient` and `ApiClientsClient` — one class per EE feature, each
 * extending `BaseApiClient`. Keeping RBAC on its own client avoids
 * pulling `RoleRead` & friends into core's dependency graph.
 *
 * URL surface: `ee/backend/src/rhesis/backend/ee/rbac/router.py`.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import type {
  RoleRead,
  RoleCreate,
  RoleUpdate,
  OrgMemberRead,
  OrgRoleAssign,
  ProjectMemberRoleRead,
  ProjectMemberRoleAssign,
  UserProjectMembershipRead,
} from '../types';

const BASE = '/rbac';

export class RbacClient extends BaseApiClient {
  constructor(sessionToken: string) {
    super(sessionToken);
  }

  // -- Role catalog ----------------------------------------------------------

  async getRoles(): Promise<RoleRead[]> {
    return this.fetch<RoleRead[]>(`${BASE}/roles`);
  }

  async getRole(roleId: string): Promise<RoleRead> {
    return this.fetch<RoleRead>(`${BASE}/roles/${roleId}`);
  }

  async createRole(body: RoleCreate): Promise<RoleRead> {
    return this.fetch<RoleRead>(`${BASE}/roles`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async updateRole(roleId: string, body: RoleUpdate): Promise<RoleRead> {
    return this.fetch<RoleRead>(`${BASE}/roles/${roleId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  async deleteRole(roleId: string): Promise<void> {
    return this.fetch<void>(`${BASE}/roles/${roleId}`, {
      method: 'DELETE',
    });
  }

  // -- Organization-level role assignment ------------------------------------

  async getOrganizationMembers(): Promise<OrgMemberRead[]> {
    return this.fetch<OrgMemberRead[]>(`${BASE}/organization-members`);
  }

  async assignOrgRole(
    userId: string,
    body: OrgRoleAssign
  ): Promise<OrgMemberRead> {
    return this.fetch<OrgMemberRead>(
      `${BASE}/organization-members/${userId}/role`,
      { method: 'PUT', body: JSON.stringify(body) }
    );
  }

  async removeOrgMember(userId: string): Promise<void> {
    return this.fetch<void>(`${BASE}/organization-members/${userId}`, {
      method: 'DELETE',
    });
  }

  // -- Project-level role assignment -----------------------------------------

  async getProjectMembers(projectId: string): Promise<ProjectMemberRoleRead[]> {
    return this.fetch<ProjectMemberRoleRead[]>(
      `${BASE}/projects/${projectId}/members`
    );
  }

  async getUserProjectMemberships(
    userId: string
  ): Promise<UserProjectMembershipRead[]> {
    return this.fetch<UserProjectMembershipRead[]>(
      `${BASE}/organization-members/${userId}/project-memberships`
    );
  }

  async assignProjectRole(
    projectId: string,
    userId: string,
    body: ProjectMemberRoleAssign
  ): Promise<ProjectMemberRoleRead> {
    return this.fetch<ProjectMemberRoleRead>(
      `${BASE}/projects/${projectId}/members/${userId}/role`,
      { method: 'PUT', body: JSON.stringify(body) }
    );
  }
}
