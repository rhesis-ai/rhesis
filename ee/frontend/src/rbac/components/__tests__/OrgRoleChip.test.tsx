/**
 * OrgRoleChip — org-level role chip/selector in the team members grid.
 *
 * Covers the reviewer-flagged regression (unlicensed fetch no longer hangs in
 * the loading skeleton — OrgRoleChip.tsx:73-79), the read-only own-row branch
 * (144-159), and the error toast on a failed role change (122-129).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Imported first (before anything that transitively loads rbac-client.ts,
// e.g. the cache modules below) so the jest.mock factories close over
// already-initialized bindings rather than racing module evaluation order.
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

import { invalidateOrgMembers } from '../../api/org-members-cache';
import { invalidateRoles } from '../../api/role-cache';
import type { OrgMemberRead } from '../../types';

import OrgRoleChip from '../OrgRoleChip';

const SESSION_TOKEN = 'session-token';
const USER_ID = 'user-1';

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

function member(overrides: Partial<OrgMemberRead> = {}): OrgMemberRead {
  return {
    id: 'member-1',
    organization_id: 'org-1',
    user_id: USER_ID,
    role_id: VIEWER_ROLE.id,
    role: VIEWER_ROLE,
    ...overrides,
  };
}

beforeEach(() => {
  resetRbacMocks();
  invalidateOrgMembers();
  invalidateRoles();
  rbacClientInstanceMock.getRoles.mockResolvedValue([VIEWER_ROLE, ADMIN_ROLE]);
});

describe('OrgRoleChip', () => {
  it('exits the loading skeleton when the members fetch fails (unlicensed/404)', async () => {
    rbacClientInstanceMock.getOrganizationMembers.mockRejectedValue(
      new Error('Not Found')
    );

    render(<OrgRoleChip userId={USER_ID} sessionToken={SESSION_TOKEN} />);

    // Falls through to the assignable Select instead of hanging forever.
    expect(await screen.findByText('Assign role')).toBeInTheDocument();
  });

  it('renders a read-only chip for the caller’s own row', async () => {
    rbacClientInstanceMock.getOrganizationMembers.mockResolvedValue([member()]);

    render(
      <OrgRoleChip
        userId={USER_ID}
        sessionToken={SESSION_TOKEN}
        currentUserId={USER_ID}
      />
    );

    expect(await screen.findByText('Viewer')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('shows an error toast when a role change is rejected', async () => {
    const user = userEvent.setup();
    rbacClientInstanceMock.getOrganizationMembers.mockResolvedValue([member()]);
    rbacClientInstanceMock.assignOrgRole.mockRejectedValue(
      new Error('Cannot demote the last Owner of an organization')
    );
    const show = jest.fn();
    notificationsMock.useNotifications.mockReturnValue({ show });

    render(<OrgRoleChip userId={USER_ID} sessionToken={SESSION_TOKEN} />);

    await user.click(await screen.findByText('Viewer'));
    await user.click(await screen.findByRole('option', { name: 'Admin' }));

    await waitFor(() => {
      expect(show).toHaveBeenCalledWith(
        'Cannot demote the last Owner of an organization',
        { severity: 'error' }
      );
    });
  });
});
