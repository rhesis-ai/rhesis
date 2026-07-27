/**
 * Shared mock factories for RBAC UI component tests.
 *
 * Jest hoists `jest.mock(...)` per test file, so this module cannot call
 * `jest.mock` on a consuming file's behalf. Instead it exports the mock
 * *implementations* — each component test file wires them in with its own
 * `jest.mock('module', () => require('.../_mocks').xyzMock)` calls, then
 * overrides individual jest.fn() return values per test as needed.
 *
 * Call `resetRbacMocks()` in `beforeEach` to clear call history and restore
 * the permissive defaults below.
 */

import React from 'react';
import type { RoleRead } from '../types';

// ---------------------------------------------------------------------------
// @/components/common/Can
// ---------------------------------------------------------------------------

export const canMock = {
  can: jest.fn(
    (
      _subject: { permitted_actions?: string[] } | null | undefined,
      _capability: string
    ) => true
  ),
  useCan: jest.fn((_capability?: string) => true),
  useCanWithStatus: jest.fn(() => ({ allowed: true, loading: false })),
  // Ambient-only stub (no `subject` support): mirrors useCan so a single
  // `canMock.useCan.mockReturnValue(false)` drives both the hook and the
  // declarative wrapper consistently within a test.
  Can: ({
    capability,
    children,
  }: {
    capability?: string;
    children: React.ReactNode;
  }) => (canMock.useCan(capability) ? <>{children}</> : null),
};

// ---------------------------------------------------------------------------
// @/contexts/FeaturesContext
// ---------------------------------------------------------------------------

export const featuresMock = {
  useFeature: jest.fn(() => true),
};

// ---------------------------------------------------------------------------
// @/contexts/OrgSettingsContext
// ---------------------------------------------------------------------------

export const FAKE_SESSION_TOKEN = 'test-session-token';
export const FAKE_ORG_ID = '00000000-0000-0000-0000-0000000000aa';

export const orgSettingsMock = {
  useOrgSettings: jest.fn(() => ({
    organization: {
      id: FAKE_ORG_ID,
      name: 'Test Org',
      createdAt: new Date(0).toISOString(),
      owner_id: '00000000-0000-0000-0000-0000000000ff',
      user_id: '00000000-0000-0000-0000-0000000000ff',
    },
    onUpdate: jest.fn(),
  })),
};

// ---------------------------------------------------------------------------
// @/components/common/NotificationContext
// ---------------------------------------------------------------------------

export const notificationsMock = {
  useNotifications: jest.fn(() => ({ show: jest.fn() })),
};

// ---------------------------------------------------------------------------
// ee/frontend rbac/hooks/useActorAuthority — permissive (Owner-equivalent) by
// default so maxLevel gating doesn't block tests that don't care about it.
// ---------------------------------------------------------------------------

export const actorAuthorityMock = {
  useActorAuthority: jest.fn(() => ({
    level: 100,
    permissionNames: new Set<string>(),
  })),
};

// ---------------------------------------------------------------------------
// next-auth/react — used indirectly via the real useActorAuthority in any
// test that does NOT mock that hook module directly.
// ---------------------------------------------------------------------------

export const FAKE_USER_ID = '00000000-0000-0000-0000-0000000000ff';

export const nextAuthMock = {
  useSession: jest.fn(() => ({
    data: { user: { id: FAKE_USER_ID } },
    status: 'authenticated',
  })),
};

// ---------------------------------------------------------------------------
// RbacClient — component tests construct `new RbacClient()`
// themselves, so the mock module must export a jest.fn() *constructor* whose
// instances share one set of method mocks.
// ---------------------------------------------------------------------------

export const rbacClientInstanceMock = {
  getRoles: jest.fn().mockResolvedValue([]),
  getRole: jest.fn(),
  createRole: jest.fn(),
  updateRole: jest.fn(),
  deleteRole: jest.fn(),
  getOrganizationMembers: jest.fn().mockResolvedValue([]),
  assignOrgRole: jest.fn(),
  removeOrgMember: jest.fn(),
  getProjectMembers: jest.fn().mockResolvedValue([]),
  assignProjectRole: jest.fn(),
};

export const rbacClientMock = {
  RbacClient: jest.fn().mockImplementation(() => rbacClientInstanceMock),
};

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

export function makeRole(overrides: Partial<RoleRead> = {}): RoleRead {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    name: 'viewer',
    display_name: 'Viewer',
    description: 'Read-only access.',
    scope: 'organization',
    level: 40,
    is_built_in: true,
    organization_id: null,
    permissions: [],
    member_count: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

/** Reset all shared mocks to their permissive defaults. Call in beforeEach. */
export function resetRbacMocks() {
  canMock.can.mockReset().mockReturnValue(true);
  canMock.useCan.mockReset().mockReturnValue(true);
  canMock.useCanWithStatus
    .mockReset()
    .mockReturnValue({ allowed: true, loading: false });
  featuresMock.useFeature.mockReset().mockReturnValue(true);
  orgSettingsMock.useOrgSettings.mockReset().mockReturnValue({
    organization: {
      id: FAKE_ORG_ID,
      name: 'Test Org',
      createdAt: new Date(0).toISOString(),
      owner_id: '00000000-0000-0000-0000-0000000000ff',
      user_id: '00000000-0000-0000-0000-0000000000ff',
    },
    onUpdate: jest.fn(),
  });
  notificationsMock.useNotifications
    .mockReset()
    .mockReturnValue({ show: jest.fn() });
  actorAuthorityMock.useActorAuthority
    .mockReset()
    .mockReturnValue({ level: 100, permissionNames: new Set<string>() });
  nextAuthMock.useSession.mockReset().mockReturnValue({
    data: { user: { id: FAKE_USER_ID } },
    status: 'authenticated',
  });
  Object.values(rbacClientInstanceMock).forEach(fn => fn.mockReset());
  rbacClientInstanceMock.getRoles.mockResolvedValue([]);
  rbacClientInstanceMock.getOrganizationMembers.mockResolvedValue([]);
  rbacClientInstanceMock.getProjectMembers.mockResolvedValue([]);
}
