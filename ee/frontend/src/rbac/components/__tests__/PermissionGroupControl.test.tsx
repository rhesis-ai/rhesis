/**
 * PermissionGroupControl — segmented None/View/Edit/Manage toggle for one
 * resource area, capped by `maxLevel` (~116-122): levels above the actor's
 * own access render disabled with an "Above your own access" title.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import PermissionGroupControl from '../PermissionGroupControl';
import { RESOURCE_AREAS, CapabilityLevel, type ResourceArea } from '../../capability-groups';

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
});
