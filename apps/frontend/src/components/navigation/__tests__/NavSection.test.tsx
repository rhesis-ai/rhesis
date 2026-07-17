import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NavSection } from '../NavSection';
import { type NavigationPageItem } from '@/types/navigation';
import {
  useAmbientPermissions,
  type AmbientPermissions,
} from '@/contexts/PermissionsContext';

// Mock the ambient subject so we can drive enabled/loading/caps directly,
// matching the pattern used in components/common/__tests__/Can.test.tsx.
jest.mock('@/contexts/PermissionsContext', () => ({
  useAmbientPermissions: jest.fn(),
}));
const mockAmbient = useAmbientPermissions as unknown as jest.Mock;

function setAmbient(partial: Partial<AmbientPermissions>) {
  mockAmbient.mockReturnValue({
    permitted_actions: [],
    loading: false,
    error: null,
    enabled: true,
    ...partial,
  });
}

function makeItem(
  segment: string,
  requiredPermission?: string
): NavigationPageItem {
  return {
    kind: 'page',
    segment,
    title: segment,
    requiredPermission,
  };
}

const header = { kind: 'header' as const, title: 'CONNECT' };

describe('NavSection', () => {
  it('hides the section entirely when every item is denied', () => {
    setAmbient({ enabled: true, permitted_actions: [] });
    render(
      <NavSection
        header={header}
        items={[
          makeItem('endpoints', 'endpoint:read'),
          makeItem('models', 'model:read'),
        ]}
        collapsed={false}
      />
    );

    expect(screen.queryByText('CONNECT')).not.toBeInTheDocument();
    expect(screen.queryByText('endpoints')).not.toBeInTheDocument();
  });

  it('renders the section when at least one item is permitted', () => {
    setAmbient({ enabled: true, permitted_actions: ['endpoint:read'] });
    render(
      <NavSection
        header={header}
        items={[
          makeItem('endpoints', 'endpoint:read'),
          makeItem('models', 'model:read'),
        ]}
        collapsed={false}
      />
    );

    expect(screen.getByText('CONNECT')).toBeInTheDocument();
    expect(screen.getByText('endpoints')).toBeInTheDocument();
    expect(screen.queryByText('models')).not.toBeInTheDocument();
  });

  it('renders items that require no permission even when all gated items are denied', () => {
    setAmbient({ enabled: true, permitted_actions: [] });
    render(
      <NavSection
        header={header}
        items={[makeItem('knowledge'), makeItem('models', 'model:read')]}
        collapsed={false}
      />
    );

    expect(screen.getByText('CONNECT')).toBeInTheDocument();
    expect(screen.getByText('knowledge')).toBeInTheDocument();
    expect(screen.queryByText('models')).not.toBeInTheDocument();
  });

  it('hides the section while ambient permissions are still loading', () => {
    setAmbient({ enabled: true, loading: true, permitted_actions: [] });
    render(
      <NavSection
        header={header}
        items={[makeItem('endpoints', 'endpoint:read')]}
        collapsed={false}
      />
    );

    expect(screen.queryByText('CONNECT')).not.toBeInTheDocument();
  });

  it('renders permissively when RBAC is off, even with no permitted_actions', () => {
    setAmbient({ enabled: false, loading: false, permitted_actions: [] });
    render(
      <NavSection
        header={header}
        items={[makeItem('endpoints', 'endpoint:read')]}
        collapsed={false}
      />
    );

    expect(screen.getByText('CONNECT')).toBeInTheDocument();
    expect(screen.getByText('endpoints')).toBeInTheDocument();
  });

  it('shows an item when any requiredAnyOf capability is present', () => {
    setAmbient({ enabled: true, permitted_actions: ['telemetry:read'] });
    render(
      <NavSection
        header={header}
        items={[
          {
            kind: 'page',
            segment: 'annotations',
            title: 'annotations',
            requiredAnyOf: ['test_result:read', 'telemetry:read'],
          },
        ]}
        collapsed={false}
      />
    );

    expect(screen.getByText('annotations')).toBeInTheDocument();
  });

  it('hides an item when no requiredAnyOf capability is present', () => {
    setAmbient({ enabled: true, permitted_actions: [] });
    render(
      <NavSection
        header={header}
        items={[
          {
            kind: 'page',
            segment: 'annotations',
            title: 'annotations',
            requiredAnyOf: ['test_result:read', 'telemetry:read'],
          },
        ]}
        collapsed={false}
      />
    );

    expect(screen.queryByText('CONNECT')).not.toBeInTheDocument();
    expect(screen.queryByText('annotations')).not.toBeInTheDocument();
  });
});
