/**
 * ProjectRoleChip — project-level role selector in the project members grid.
 *
 * Mirrors OrgRoleChip.test.tsx's shape (loading/404-exits-skeleton/assign
 * flow), including the read-only branch: it's gated by
 * `can(memberEntry, Capability.Member.MANAGE)`, a pure membership check
 * against `memberEntry.permitted_actions` — the backend
 * (`_member_permitted_actions` in router.py) is the single source of truth
 * for self-change/outranking/ambient-permission logic, not this component.
 * Tests that exercise that branch override `canMock.can` with a real
 * membership check so the mock doesn't mask a component regression.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {
  canMock,
  featuresMock,
  notificationsMock,
  actorAuthorityMock,
  rbacClientMock,
  rbacClientInstanceMock,
  resetRbacMocks,
  makeRole,
} from '../../__mocks__/_mocks';

jest.mock('@/components/common/Can', () => canMock);
jest.mock('@/contexts/FeaturesContext', () => featuresMock);
jest.mock('@/components/common/NotificationContext', () => notificationsMock);
jest.mock('../../hooks/useActorAuthority', () => actorAuthorityMock);
jest.mock('../../api/rbac-client', () => rbacClientMock);

import {
  invalidateProjectMembers,
  getCachedProjectMembers,
} from '../../api/project-members-cache';
import { invalidateRoles } from '../../api/role-cache';
import type { ProjectMemberRoleRead } from '../../types';

import ProjectRoleChip from '../ProjectRoleChip';

const SESSION_TOKEN = 'session-token';
const USER_ID = 'user-1';
const PROJECT_ID = 'project-1';

const VIEWER_ROLE = makeRole({
  id: 'role-viewer',
  name: 'viewer',
  display_name: 'Viewer',
  level: 40,
});
const ADMIN_ROLE = makeRole({
  id: 'role-admin',
  name: 'admin',
  display_name: 'Admin',
  level: 80,
});

function member(
  overrides: Partial<ProjectMemberRoleRead> = {}
): ProjectMemberRoleRead {
  return {
    project_id: PROJECT_ID,
    user_id: USER_ID,
    role_id: null,
    role: null,
    permitted_actions: ['member:manage'],
    ...overrides,
  };
}

/** Mirrors the real `can()` in `@/utils/affordances`: pure membership check
 *  against `subject.permitted_actions`. Tests that care about the
 *  read-only/editable branch install this so the mock doesn't just return
 *  `true` unconditionally and mask a regression in that branch. */
function useRealCanImplementation() {
  canMock.can.mockImplementation(
    (
      subject: { permitted_actions?: string[] } | null | undefined,
      capability: string
    ) => subject?.permitted_actions?.includes(capability) ?? false
  );
}

beforeEach(() => {
  resetRbacMocks();
  invalidateProjectMembers(SESSION_TOKEN, PROJECT_ID);
  invalidateRoles();
  rbacClientInstanceMock.getRoles.mockResolvedValue([VIEWER_ROLE, ADMIN_ROLE]);
  // Sanity: the cache really is empty between tests, so `loading` starts true.
  expect(getCachedProjectMembers(SESSION_TOKEN, PROJECT_ID)).toEqual([]);
});

describe('ProjectRoleChip', () => {
  it('exits the loading skeleton when the members fetch fails (unlicensed/404)', async () => {
    rbacClientInstanceMock.getProjectMembers.mockRejectedValue(
      new Error('Not Found')
    );

    render(
      <ProjectRoleChip
        userId={USER_ID}
        projectId={PROJECT_ID}
        sessionToken={SESSION_TOKEN}
      />
    );

    // Falls through to the assignable Select instead of hanging forever.
    expect(await screen.findByText('Assign role')).toBeInTheDocument();
  });

  it('renders a read-only chip when permitted_actions excludes member:manage', async () => {
    // The backend returns an empty permitted_actions for the caller's own
    // row or an outranked member (e.g. a project Admin viewing a project
    // Owner) — the component treats both identically via `can()`.
    useRealCanImplementation();
    rbacClientInstanceMock.getProjectMembers.mockResolvedValue([
      member({
        role_id: ADMIN_ROLE.id,
        role: ADMIN_ROLE,
        permitted_actions: [],
      }),
    ]);

    render(
      <ProjectRoleChip
        userId={USER_ID}
        projectId={PROJECT_ID}
        sessionToken={SESSION_TOKEN}
      />
    );

    expect(await screen.findByText('Admin')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('renders an editable select when permitted_actions includes member:manage', async () => {
    useRealCanImplementation();
    rbacClientInstanceMock.getProjectMembers.mockResolvedValue([
      member({ permitted_actions: ['member:manage'] }),
    ]);

    render(
      <ProjectRoleChip
        userId={USER_ID}
        projectId={PROJECT_ID}
        sessionToken={SESSION_TOKEN}
      />
    );

    expect(await screen.findByRole('combobox')).toBeInTheDocument();
  });

  it('assigns a role and shows the updated value', async () => {
    const user = userEvent.setup();
    rbacClientInstanceMock.getProjectMembers
      .mockResolvedValueOnce([member()])
      .mockResolvedValueOnce([
        member({ role_id: ADMIN_ROLE.id, role: ADMIN_ROLE }),
      ]);
    rbacClientInstanceMock.assignProjectRole.mockResolvedValue(undefined);
    const show = jest.fn();
    notificationsMock.useNotifications.mockReturnValue({ show });

    render(
      <ProjectRoleChip
        userId={USER_ID}
        projectId={PROJECT_ID}
        sessionToken={SESSION_TOKEN}
      />
    );

    await user.click(await screen.findByText('Assign role'));
    await user.click(await screen.findByRole('option', { name: 'Admin' }));

    await waitFor(() => {
      expect(rbacClientInstanceMock.assignProjectRole).toHaveBeenCalledWith(
        PROJECT_ID,
        USER_ID,
        { role_id: ADMIN_ROLE.id }
      );
    });
    expect(await screen.findByText('Admin')).toBeInTheDocument();
    expect(show).toHaveBeenCalledWith('Project role updated', {
      severity: 'success',
    });
  });

  it('shows an error toast when a role change is rejected', async () => {
    const user = userEvent.setup();
    rbacClientInstanceMock.getProjectMembers.mockResolvedValue([member()]);
    rbacClientInstanceMock.assignProjectRole.mockRejectedValue(
      new Error('Role level exceeds your own authority')
    );
    const show = jest.fn();
    notificationsMock.useNotifications.mockReturnValue({ show });

    render(
      <ProjectRoleChip
        userId={USER_ID}
        projectId={PROJECT_ID}
        sessionToken={SESSION_TOKEN}
      />
    );

    await user.click(await screen.findByText('Assign role'));
    await user.click(await screen.findByRole('option', { name: 'Admin' }));

    await waitFor(() => {
      expect(show).toHaveBeenCalledWith(
        'Role level exceeds your own authority',
        { severity: 'error' }
      );
    });
  });
});
