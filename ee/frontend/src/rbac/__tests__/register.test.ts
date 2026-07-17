/**
 * Focused tests for register.tsx's `prewarmCaches` / `prewarmProjectCaches`.
 *
 * These gate `GET /rbac/roles` behind `canManageRoles`, since that endpoint
 * requires `Permission.Role.READ`, which viewers without member-management
 * rights don't hold — fetching it unconditionally would fire a doomed 403 on
 * every non-admin page load (see TeamMembersGrid.tsx / ProjectMembers.tsx).
 * Org/project members are always fetched: every role chip needs them
 * regardless of the viewer's own permissions.
 */

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
}));

jest.mock('../api/org-members-cache', () => ({
  fetchOrgMembers: jest.fn(),
}));
jest.mock('../api/project-members-cache', () => ({
  fetchProjectMembers: jest.fn(),
}));
jest.mock('../api/role-cache', () => ({
  fetchRoles: jest.fn(),
}));

import {
  getMemberRoleExtensions,
  resetMemberRoleExtensions,
} from '@/lib/extension-registries';
import { registerRBAC } from '../register';
import { fetchOrgMembers } from '../api/org-members-cache';
import { fetchProjectMembers } from '../api/project-members-cache';
import { fetchRoles } from '../api/role-cache';

const PROJECT_ID = 'project-1';

describe('register.tsx — prewarm caches', () => {
  beforeEach(() => {
    resetMemberRoleExtensions();
    jest.clearAllMocks();
    registerRBAC();
  });

  describe('prewarmCaches', () => {
    it('always fetches org members', () => {
      getMemberRoleExtensions().prewarmCaches?.();
      expect(fetchOrgMembers).toHaveBeenCalled();
    });

    it('fetches roles when canManageRoles is true', () => {
      getMemberRoleExtensions().prewarmCaches?.({ canManageRoles: true });
      expect(fetchRoles).toHaveBeenCalled();
    });

    it('does not fetch roles when canManageRoles is false or omitted', () => {
      getMemberRoleExtensions().prewarmCaches?.({ canManageRoles: false });
      getMemberRoleExtensions().prewarmCaches?.();
      expect(fetchRoles).not.toHaveBeenCalled();
    });
  });

  describe('prewarmProjectCaches', () => {
    it('always fetches project members', () => {
      getMemberRoleExtensions().prewarmProjectCaches?.(PROJECT_ID);
      expect(fetchProjectMembers).toHaveBeenCalledWith(PROJECT_ID);
    });

    it('fetches roles when canManageRoles is true', () => {
      getMemberRoleExtensions().prewarmProjectCaches?.(PROJECT_ID, {
        canManageRoles: true,
      });
      expect(fetchRoles).toHaveBeenCalled();
    });

    it('does not fetch roles when canManageRoles is false or omitted', () => {
      getMemberRoleExtensions().prewarmProjectCaches?.(PROJECT_ID, {
        canManageRoles: false,
      });
      getMemberRoleExtensions().prewarmProjectCaches?.(PROJECT_ID);
      expect(fetchRoles).not.toHaveBeenCalled();
    });
  });
});
