/**
 * RoleSummary — plain-language "this role can" summary for a permission set.
 * Purely presentational (no hooks/context), driven by
 * `summarizePermissions()` in ../../capability-groups.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { RESOURCE_AREAS, CapabilityLevel } from '../../capability-groups';
import RoleSummary from '../RoleSummary';

function requireArea(id: string) {
  const area = RESOURCE_AREAS.find(a => a.id === id);
  if (!area) throw new Error(`Unknown resource area: ${id}`);
  return area;
}

describe('RoleSummary', () => {
  it('shows the empty-permissions message when the set is empty', () => {
    render(<RoleSummary permissions={new Set()} />);

    expect(
      screen.getByText('No permissions yet. Set access levels above to build the role.')
    ).toBeInTheDocument();
  });

  it('summarizes a granted area and lists other areas as denied', () => {
    const testResources = requireArea('test-resources');
    const permissions = new Set(testResources.levels[CapabilityLevel.VIEW]);

    render(<RoleSummary permissions={permissions} />);

    expect(screen.getByText('Test Resources: read-only')).toBeInTheDocument();

    const otherArea = RESOURCE_AREAS.find(a => a.id !== 'test-resources');
    if (!otherArea) throw new Error('Expected a second resource area to exist');
    expect(
      screen.getByText(`No access to ${otherArea.label.toLowerCase()}`)
    ).toBeInTheDocument();
  });
});
