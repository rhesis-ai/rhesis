/**
 * RoleEditorDrawer — create/edit/view a custom role.
 *
 * Covers slug generation (line ~133), 409-conflict messaging (~152-160),
 * delete gated on `!role.is_built_in` (~207-211) with a built-in-role Alert,
 * and `maxLevel={levelForArea(actorPermissions, area)}` wired down to
 * PermissionGroupControl (~307) — the reviewer's "computed but never passed"
 * finding, now wired.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {
  orgSettingsMock,
  notificationsMock,
  actorAuthorityMock,
  rbacClientMock,
  rbacClientInstanceMock,
  resetRbacMocks,
  makeRole,
} from '../../__mocks__/_mocks';

jest.mock('@/contexts/OrgSettingsContext', () => orgSettingsMock);
jest.mock('@/components/common/NotificationContext', () => notificationsMock);
jest.mock('../../hooks/useActorAuthority', () => actorAuthorityMock);
jest.mock('../../api/rbac-client', () => rbacClientMock);

// Stub out the (separately-tested) permission grid so these tests only
// assert the props RoleEditorDrawer computes and passes down, not its
// internal rendering.
jest.mock('../PermissionGroupControl', () => ({
  __esModule: true,
  default: ({ area, maxLevel }: { area: { id: string }; maxLevel: number }) => (
    <div data-testid={`area-${area.id}`} data-max-level={maxLevel} />
  ),
}));

import { RESOURCE_AREAS, CapabilityLevel } from '../../capability-groups';
import RoleEditorDrawer from '../RoleEditorDrawer';

const CUSTOM_ROLE = makeRole({
  id: 'role-custom',
  name: 'auditor',
  display_name: 'Auditor',
  is_built_in: false,
  level: 30,
  member_count: 2,
});

const BUILT_IN_ROLE = makeRole({
  id: 'role-viewer',
  name: 'viewer',
  display_name: 'Viewer',
  is_built_in: true,
  level: 40,
});

beforeEach(() => {
  resetRbacMocks();
});

describe('RoleEditorDrawer', () => {
  it('slugifies the display name into a lowercase, underscored role name on create', async () => {
    const user = userEvent.setup();
    rbacClientInstanceMock.createRole.mockResolvedValue(CUSTOM_ROLE);

    render(
      <RoleEditorDrawer open mode="create" onClose={jest.fn()} onSaved={jest.fn()} />
    );

    await user.type(screen.getByLabelText(/role name/i), 'Data Reader Team');
    await user.click(screen.getByRole('button', { name: /create role/i }));

    await waitFor(() => {
      expect(rbacClientInstanceMock.createRole).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'data_reader_team' })
      );
    });
  });

  it('shows a conflict message when the backend returns 409', async () => {
    const user = userEvent.setup();
    const conflict = Object.assign(new Error('conflict'), { status: 409 });
    rbacClientInstanceMock.createRole.mockRejectedValue(conflict);

    render(
      <RoleEditorDrawer open mode="create" onClose={jest.fn()} onSaved={jest.fn()} />
    );

    await user.type(screen.getByLabelText(/role name/i), 'Auditor');
    await user.click(screen.getByRole('button', { name: /create role/i }));

    expect(
      await screen.findByText('A role with this name already exists')
    ).toBeInTheDocument();
  });

  it('offers delete for a custom role but not for a built-in role', () => {
    const { rerender } = render(
      <RoleEditorDrawer
        open
        mode="edit"
        role={CUSTOM_ROLE}
        onClose={jest.fn()}
      />
    );
    expect(
      screen.getByRole('button', { name: /delete role/i })
    ).toBeInTheDocument();

    rerender(
      <RoleEditorDrawer
        open
        mode="view"
        role={BUILT_IN_ROLE}
        onClose={jest.fn()}
      />
    );
    expect(
      screen.queryByRole('button', { name: /delete role/i })
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/permissions for built-in roles are fixed/i)
    ).toBeInTheDocument();
  });

  it('passes levelForArea(actorPermissions, area) as maxLevel to the permission grid', () => {
    const testResourcesArea = RESOURCE_AREAS.find(a => a.id === 'test-resources');
    if (!testResourcesArea) throw new Error('test-resources area not found');
    const viewOnlyCaps = testResourcesArea.levels[CapabilityLevel.VIEW];
    actorAuthorityMock.useActorAuthority.mockReturnValue({
      level: 100,
      permissionNames: new Set(viewOnlyCaps),
    });

    render(
      <RoleEditorDrawer open mode="create" onClose={jest.fn()} onSaved={jest.fn()} />
    );

    expect(screen.getByTestId('area-test-resources')).toHaveAttribute(
      'data-max-level',
      String(CapabilityLevel.VIEW)
    );
  });
});
