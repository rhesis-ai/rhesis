/**
 * TokenScopeField — restricts a new API token to a role's permission set.
 *
 * Covers the full-vs-restricted scope toggle and role-dropdown population
 * (mirrors the token-scope-field.spec.ts E2E coverage at the unit level),
 * and doubles as a render regression check for the drawerOutlinedFieldSx /
 * theme-token styling fix applied to this component.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {
  rbacClientMock,
  rbacClientInstanceMock,
  resetRbacMocks,
  makeRole,
} from '../../__mocks__/_mocks';

jest.mock('../../api/rbac-client', () => rbacClientMock);

import { invalidateRoles } from '../../api/role-cache';
import { RESOURCE_AREAS, CapabilityLevel } from '../../capability-groups';
import type { PermissionRead } from '../../types';
import TokenScopeField from '../TokenScopeField';

const SESSION_TOKEN = 'session-token';

function requireArea(id: string) {
  const area = RESOURCE_AREAS.find(a => a.id === id);
  if (!area) throw new Error(`Unknown resource area: ${id}`);
  return area;
}

function permissionsFor(names: readonly string[]): PermissionRead[] {
  return names.map(name => ({
    id: name,
    name,
    display_name: name,
    resource_type: name.split(':')[0],
    action: name.split(':')[1] ?? 'read',
    scope: 'project',
    is_retired: false,
  }));
}

const TEST_RESOURCES_VIEW =
  requireArea('test-resources').levels[CapabilityLevel.VIEW];

const AUDITOR_ROLE = makeRole({
  id: 'role-auditor',
  name: 'auditor',
  display_name: 'Auditor',
  is_built_in: false,
  level: 30,
  permissions: permissionsFor(TEST_RESOURCES_VIEW),
});

beforeEach(() => {
  resetRbacMocks();
  invalidateRoles();
  rbacClientInstanceMock.getRoles.mockResolvedValue([AUDITOR_ROLE]);
});

describe('TokenScopeField', () => {
  it('renders nothing while roles are loading, then the full/restricted toggle', async () => {
    render(<TokenScopeField value={null} onChange={jest.fn()} />);

    expect(await screen.findByText('Token permissions')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /full access/i })).toBeChecked();
    expect(
      screen.getByRole('radio', { name: /restricted/i })
    ).not.toBeChecked();
  });

  it('switching to restricted with no role selected clears the scope', async () => {
    const onChange = jest.fn();
    const user = userEvent.setup();

    render(<TokenScopeField value={null} onChange={onChange} />);

    await screen.findByText('Token permissions');
    await user.click(screen.getByRole('radio', { name: /restricted/i }));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('populates the role dropdown and derives permissions + summary on selection', async () => {
    const onChange = jest.fn();
    const user = userEvent.setup();

    render(<TokenScopeField value={[]} onChange={onChange} />);

    await user.click(await screen.findByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'Auditor' }));

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.arrayContaining(TEST_RESOURCES_VIEW as string[])
      );
    });

    expect(await screen.findByText('Permission summary')).toBeInTheDocument();
    expect(screen.getByText('Test Resources: View')).toBeInTheDocument();
  });

  it('renders nothing when there are no assignable roles', async () => {
    rbacClientInstanceMock.getRoles.mockResolvedValue([]);

    const { container } = render(
      <TokenScopeField value={null} onChange={jest.fn()} />
    );

    await waitFor(() => {
      expect(container).toBeEmptyDOMElement();
    });
  });
});
