/**
 * RoleSelectField — project role picker used in the "add member" drawer.
 *
 * Covers the loading skeleton before the roles fetch resolves, the empty
 * state when no assignable roles come back, and the default-to-Member
 * selection (value=null renders the "Default (Member)" placeholder item).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {
  actorAuthorityMock,
  rbacClientMock,
  rbacClientInstanceMock,
  resetRbacMocks,
  makeRole,
} from '../../__mocks__/_mocks';

jest.mock('../../hooks/useActorAuthority', () => actorAuthorityMock);
jest.mock('../../api/rbac-client', () => rbacClientMock);

import { invalidateRoles } from '../../api/role-cache';
import RoleSelectField from '../RoleSelectField';

const SESSION_TOKEN = 'session-token';

const VIEWER_ROLE = makeRole({
  id: 'role-viewer',
  name: 'viewer',
  display_name: 'Viewer',
  level: 40,
});
const MEMBER_ROLE = makeRole({
  id: 'role-member',
  name: 'member',
  display_name: 'Member',
  level: 60,
});
const NONE_ROLE = makeRole({
  id: 'role-none',
  name: 'none',
  display_name: 'None',
  level: 0,
});

beforeEach(() => {
  resetRbacMocks();
  invalidateRoles();
});

describe('RoleSelectField', () => {
  it('shows a loading skeleton before the roles fetch resolves', async () => {
    // Resolved at the end of the test, not left dangling: role-cache.ts's
    // module-level `_rolesPending` is only cleared when the promise it
    // wraps settles, and `invalidateRoles()` does not touch it — an
    // eternally-pending mock here would starve every later test in this
    // file of a fresh fetch.
    let resolveRoles!: (roles: ReturnType<typeof makeRole>[]) => void;
    rbacClientInstanceMock.getRoles.mockReturnValue(
      new Promise(resolve => {
        resolveRoles = resolve;
      })
    );

    render(
      <RoleSelectField
        sessionToken={SESSION_TOKEN}
        value={null}
        onChange={jest.fn()}
      />
    );

    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByText('Default (Member)')).not.toBeInTheDocument();

    resolveRoles([]);
    await screen.findByRole('combobox');
  });

  it('renders only the default option when no assignable roles come back', async () => {
    // None (level 0, built-in) is the only role isAssignableProjectRole
    // excludes — it means "no access", not a useful assignment.
    rbacClientInstanceMock.getRoles.mockResolvedValue([NONE_ROLE]);

    const user = userEvent.setup();
    render(
      <RoleSelectField
        sessionToken={SESSION_TOKEN}
        value={null}
        onChange={jest.fn()}
      />
    );

    await user.click(await screen.findByRole('combobox'));
    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(
      screen.getByRole('option', { name: /default \(member\)/i })
    ).toBeInTheDocument();
  });

  it('defaults to the Member placeholder option when value is null', async () => {
    rbacClientInstanceMock.getRoles.mockResolvedValue([
      VIEWER_ROLE,
      MEMBER_ROLE,
    ]);
    const user = userEvent.setup();

    render(
      <RoleSelectField
        sessionToken={SESSION_TOKEN}
        value={null}
        onChange={jest.fn()}
      />
    );

    await user.click(await screen.findByRole('combobox'));
    expect(
      screen.getByRole('option', { name: /default \(member\)/i })
    ).toHaveAttribute('aria-selected', 'true');
  });

  it('calls onChange with the selected role id', async () => {
    rbacClientInstanceMock.getRoles.mockResolvedValue([
      VIEWER_ROLE,
      MEMBER_ROLE,
    ]);
    const onChange = jest.fn();
    const user = userEvent.setup();

    render(
      <RoleSelectField
        sessionToken={SESSION_TOKEN}
        value={null}
        onChange={onChange}
      />
    );

    await user.click(await screen.findByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Viewer' }));

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(VIEWER_ROLE.id);
    });
  });
});
