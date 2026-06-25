import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Can, useCan, can } from '../Can';
import {
  useAmbientPermissions,
  type AmbientPermissions,
} from '@/contexts/PermissionsContext';

// Mock the ambient subject so we can drive enabled/loading/caps directly.
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

function Probe({ capability }: { capability: string }) {
  return <span>{useCan(capability) ? 'yes' : 'no'}</span>;
}

describe('can (pure object check)', () => {
  it('tests membership in the subject permitted_actions', () => {
    expect(
      can({ permitted_actions: ['comment:update'] }, 'comment:update')
    ).toBe(true);
    expect(can({ permitted_actions: [] }, 'comment:update')).toBe(false);
    expect(can(null, 'comment:update')).toBe(false);
  });
});

describe('useCan (ambient / scope-level)', () => {
  it('is a permissive no-op when RBAC is known off (enabled=false, not loading)', () => {
    setAmbient({ enabled: false, loading: false, permitted_actions: [] });
    render(<Probe capability="token:manage" />);
    expect(screen.getByText('yes')).toBeInTheDocument();
  });

  it('is fail-closed while RBAC status is unknown (feature flags loading)', () => {
    // enabled=false but loading=true ⇒ status unknown, must NOT fail-open.
    setAmbient({ enabled: false, loading: true });
    render(<Probe capability="token:manage" />);
    expect(screen.getByText('no')).toBeInTheDocument();
  });

  it('is fail-closed while loading when RBAC is on', () => {
    setAmbient({ enabled: true, loading: true });
    render(<Probe capability="metric:read" />);
    expect(screen.getByText('no')).toBeInTheDocument();
  });

  it('reflects the ambient capability set when RBAC is on', () => {
    setAmbient({ enabled: true, permitted_actions: ['metric:read'] });
    const { rerender } = render(<Probe capability="metric:read" />);
    expect(screen.getByText('yes')).toBeInTheDocument();
    rerender(<Probe capability="token:manage" />);
    expect(screen.getByText('no')).toBeInTheDocument();
  });
});

describe('<Can> object path is always-on (ignores enabled)', () => {
  it('renders from the subject even when RBAC is off', () => {
    setAmbient({ enabled: false });
    render(
      <Can capability="comment:update" subject={{ permitted_actions: [] }}>
        <span>edit</span>
      </Can>
    );
    // Object subject lacks the cap → hidden, regardless of the off ambient.
    expect(screen.queryByText('edit')).not.toBeInTheDocument();
  });

  it('renders ambient children permissively when RBAC is off', () => {
    setAmbient({ enabled: false });
    render(
      <Can capability="token:manage">
        <span>api-nav</span>
      </Can>
    );
    expect(screen.getByText('api-nav')).toBeInTheDocument();
  });
});
