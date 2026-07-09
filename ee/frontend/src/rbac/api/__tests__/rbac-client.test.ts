/**
 * Smoke tests for the EE RBAC API client.
 *
 * Mirrors ee/frontend/src/sso/api/__tests__/sso-client.test.ts: `BaseApiClient
 * .fetch` is mocked at the prototype level, and each method's URL/verb/body
 * is pinned so a future refactor cannot silently break the client/backend
 * contract with ee/backend/src/rhesis/backend/ee/rbac/router.py.
 *
 * Unlike SSOClient's `getSSOConfig`, no RbacClient method catches fetch
 * errors — a rejected fetch propagates, it does not resolve to null.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { RbacClient } from '../rbac-client';
import type {
  RoleCreate,
  RoleUpdate,
  OrgRoleAssign,
  ProjectMemberRoleAssign,
} from '../../types';

const FAKE_TOKEN = 'test-session-token';
const ROLE_ID = '11111111-1111-1111-1111-111111111111';
const USER_ID = '22222222-2222-2222-2222-222222222222';
const PROJECT_ID = '33333333-3333-3333-3333-333333333333';

type FetchableProto = { fetch: (...args: unknown[]) => Promise<unknown> };

describe('RbacClient', () => {
  let fetchSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;
  let client: RbacClient;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(BaseApiClient.prototype as unknown as FetchableProto, 'fetch')
      .mockResolvedValue({});
    client = new RbacClient(FAKE_TOKEN);
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('getRoles hits GET /rbac/roles', async () => {
    await client.getRoles();
    expect(fetchSpy).toHaveBeenCalledWith('/rbac/roles');
  });

  it('getRoles propagates a rejected fetch instead of swallowing it', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('unlicensed'));
    await expect(client.getRoles()).rejects.toThrow('unlicensed');
  });

  it('getRole hits GET /rbac/roles/<id>', async () => {
    await client.getRole(ROLE_ID);
    expect(fetchSpy).toHaveBeenCalledWith(`/rbac/roles/${ROLE_ID}`);
  });

  it('createRole POSTs to /rbac/roles', async () => {
    const body: RoleCreate = {
      name: 'data-reader',
      permission_names: ['test_set:read'],
    };
    await client.createRole(body);
    expect(fetchSpy).toHaveBeenCalledWith(
      '/rbac/roles',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(body) })
    );
  });

  it('updateRole PUTs to /rbac/roles/<id>', async () => {
    const body: RoleUpdate = {
      permission_names: ['test_set:read', 'test_set:update'],
    };
    await client.updateRole(ROLE_ID, body);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/roles/${ROLE_ID}`,
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(body) })
    );
  });

  it('deleteRole DELETEs /rbac/roles/<id>', async () => {
    await client.deleteRole(ROLE_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/roles/${ROLE_ID}`,
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('getOrganizationMembers hits GET /rbac/organization-members', async () => {
    await client.getOrganizationMembers();
    expect(fetchSpy).toHaveBeenCalledWith('/rbac/organization-members');
  });

  it('assignOrgRole PUTs to /rbac/organization-members/<userId>/role', async () => {
    const body: OrgRoleAssign = { role_id: ROLE_ID };
    await client.assignOrgRole(USER_ID, body);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/organization-members/${USER_ID}/role`,
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(body) })
    );
  });

  it('removeOrgMember DELETEs /rbac/organization-members/<userId>', async () => {
    await client.removeOrgMember(USER_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/organization-members/${USER_ID}`,
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('getUserProjectMemberships hits GET /rbac/organization-members/<userId>/project-memberships', async () => {
    await client.getUserProjectMemberships(USER_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/organization-members/${USER_ID}/project-memberships`
    );
  });

  it('getProjectMembers hits GET /rbac/projects/<projectId>/members', async () => {
    await client.getProjectMembers(PROJECT_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/projects/${PROJECT_ID}/members`
    );
  });

  it('assignProjectRole PUTs to /rbac/projects/<projectId>/members/<userId>/role', async () => {
    const body: ProjectMemberRoleAssign = { role_id: ROLE_ID };
    await client.assignProjectRole(PROJECT_ID, USER_ID, body);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/rbac/projects/${PROJECT_ID}/members/${USER_ID}/role`,
      expect.objectContaining({ method: 'PUT', body: JSON.stringify(body) })
    );
  });
});
