/**
 * PermissionGroupControl — segmented None/View/Edit/Manage toggle for one
 * resource area, capped by `maxLevel` (~116-122): levels above the actor's
 * own access render disabled with an "Above your own access" title.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PermissionGroupControl from '../PermissionGroupControl';
import {
  RESOURCE_AREAS,
  CapabilityLevel,
  groupAreaCapabilitiesByResource,
  type ResourceArea,
} from '../../capability-groups';
import { Capability } from '@/constants/capabilities';

function requireArea(id: string): ResourceArea {
  const area = RESOURCE_AREAS.find(a => a.id === id);
  if (!area) throw new Error(`Unknown resource area: ${id}`);
  return area;
}

const AREA = requireArea('test-resources');

describe('PermissionGroupControl', () => {
  it('enables every level up to maxLevel', () => {
    render(
      <PermissionGroupControl
        area={AREA}
        currentLevel={CapabilityLevel.NONE}
        onLevelChange={jest.fn()}
        permissions={new Set()}
        onToggleCapability={jest.fn()}
        maxLevel={CapabilityLevel.MANAGE}
      />
    );

    expect(screen.getByRole('button', { name: 'Manage' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeEnabled();
  });

  it('disables levels above maxLevel with an "Above your own access" title', () => {
    render(
      <PermissionGroupControl
        area={AREA}
        currentLevel={CapabilityLevel.NONE}
        onLevelChange={jest.fn()}
        permissions={new Set()}
        onToggleCapability={jest.fn()}
        maxLevel={CapabilityLevel.VIEW}
      />
    );

    const manageButton = screen.getByRole('button', { name: 'Manage' });
    expect(manageButton).toBeDisabled();
    expect(manageButton).toHaveAttribute('title', 'Above your own access');

    const editButton = screen.getByRole('button', { name: 'Edit' });
    expect(editButton).toBeDisabled();

    const viewButton = screen.getByRole('button', { name: 'View' });
    expect(viewButton).toBeEnabled();
    expect(viewButton).not.toHaveAttribute('title');
  });

  it('disables all levels when readOnly regardless of maxLevel', () => {
    render(
      <PermissionGroupControl
        area={AREA}
        currentLevel={CapabilityLevel.VIEW}
        onLevelChange={jest.fn()}
        permissions={new Set()}
        onToggleCapability={jest.fn()}
        maxLevel={CapabilityLevel.MANAGE}
        readOnly
      />
    );

    expect(screen.getByRole('button', { name: 'View' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Manage' })).toBeDisabled();
  });

  it('groups expanded permissions by resource with CRUD columns', async () => {
    const user = userEvent.setup();
    render(
      <PermissionGroupControl
        area={AREA}
        currentLevel={CapabilityLevel.NONE}
        onLevelChange={jest.fn()}
        permissions={new Set([Capability.TestSet.READ, Capability.Endpoint.READ])}
        onToggleCapability={jest.fn()}
        maxLevel={CapabilityLevel.MANAGE}
      />
    );

    await user.click(screen.getByRole('button', { name: /expand/i }));

    expect(screen.getByText('Test Set')).toBeInTheDocument();
    expect(screen.getByText('Endpoint')).toBeInTheDocument();
    expect(screen.getByLabelText('Test Set View')).toBeChecked();
    expect(screen.getByLabelText('Endpoint View')).toBeChecked();
    expect(screen.getByText('Generate tests')).toBeInTheDocument();
    expect(screen.queryByText('Delete own test runs')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Test Run Delete (own)')).toBeInTheDocument();
  });
});

describe('groupAreaCapabilitiesByResource', () => {
  it('maps standard CRUD capabilities and keeps extras', () => {
    const rows = groupAreaCapabilitiesByResource(AREA);
    const testSet = rows.find(r => r.resourceId === 'test_set');
    const endpoint = rows.find(r => r.resourceId === 'endpoint');

    expect(testSet).toMatchObject({
      label: 'Test Set',
      view: Capability.TestSet.READ,
      create: Capability.TestSet.CREATE,
      editAll: Capability.TestSet.UPDATE,
      deleteAll: Capability.TestSet.DELETE,
    });
    expect(testSet?.extras.map(e => e.cap)).toEqual(
      expect.arrayContaining([
        Capability.TestSet.GENERATE,
        Capability.TestSet.EXECUTE,
      ])
    );

    const testRun = rows.find(r => r.resourceId === 'test_run');
    expect(testRun?.deleteOwn).toBe(Capability.TestRun.DELETE_OWN);

    expect(endpoint).toMatchObject({
      label: 'Endpoint',
      view: Capability.Endpoint.READ,
      create: Capability.Endpoint.CREATE,
      editAll: Capability.Endpoint.UPDATE,
      deleteAll: Capability.Endpoint.DELETE,
      extras: [],
    });
  });
});
