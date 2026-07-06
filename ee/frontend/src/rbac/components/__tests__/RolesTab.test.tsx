/**
 * RolesTab — role catalog page: useCanWithStatus gate, built-in/custom split,
 * and the "New role" action gated behind Capability.Role.MANAGE.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

import {
  canMock,
  orgSettingsMock,
  notificationsMock,
  actorAuthorityMock,
  rbacClientMock,
  rbacClientInstanceMock,
  resetRbacMocks,
  makeRole,
} from '../../__mocks__/_mocks';

jest.mock('@/components/common/Can', () => canMock);
jest.mock('@/contexts/OrgSettingsContext', () => orgSettingsMock);
jest.mock('@/components/common/NotificationContext', () => notificationsMock);
jest.mock('../../hooks/useActorAuthority', () => actorAuthorityMock);
jest.mock('../../api/rbac-client', () => rbacClientMock);

import { invalidateRoles } from '../../api/role-cache';
import RolesTab from '../RolesTab';

const BUILT_IN_ROLE = makeRole({
  id: 'role-viewer',
  name: 'viewer',
  display_name: 'Viewer',
  is_built_in: true,
  level: 40,
});

const CUSTOM_ROLE = makeRole({
  id: 'role-auditor',
  name: 'auditor',
  display_name: 'Auditor',
  is_built_in: false,
  level: 30,
  member_count: 3,
});

beforeEach(() => {
  resetRbacMocks();
  invalidateRoles();
  rbacClientInstanceMock.getRoles.mockResolvedValue([BUILT_IN_ROLE, CUSTOM_ROLE]);
});

describe('RolesTab', () => {
  it('renders AccessDenied when the caller lacks role:read', async () => {
    canMock.useCanWithStatus.mockReturnValue({ allowed: false, loading: false });

    render(<RolesTab />);

    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(rbacClientInstanceMock.getRoles).not.toHaveBeenCalled();
  });

  it('splits roles into Built-in and Custom sections', async () => {
    render(<RolesTab />);

    expect(await screen.findByText('Viewer')).toBeInTheDocument();
    expect(screen.getByText('Auditor')).toBeInTheDocument();
    expect(screen.getByText('Built-in Roles')).toBeInTheDocument();
    expect(screen.getByText('Custom Roles')).toBeInTheDocument();
    // Custom-role member count is rendered in its table row.
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('hides the "New role" action when the caller lacks role:manage', async () => {
    canMock.useCan.mockReturnValue(false);

    render(<RolesTab />);

    await screen.findByText('Viewer');
    expect(
      screen.queryByRole('button', { name: /new role/i })
    ).not.toBeInTheDocument();
  });

  it('shows the "New role" action when the caller holds role:manage', async () => {
    canMock.useCan.mockReturnValue(true);

    render(<RolesTab />);

    expect(
      await screen.findByRole('button', { name: /new role/i })
    ).toBeInTheDocument();
  });
});
