import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import TokensPageClient from '../TokensPageClient';
import {
  useAmbientPermissions,
  type AmbientPermissions,
} from '@/contexts/PermissionsContext';

// The real Can/useCan run against these ambient sets, so the page sees what
// each built-in role resolves to on the backend (ee/rbac/models.py).
jest.mock('@/contexts/PermissionsContext', () => ({
  useAmbientPermissions: jest.fn(),
}));
const mockAmbient = useAmbientPermissions as unknown as jest.Mock;

const SELF_SERVICE = [
  'token:create',
  'token:read',
  'token:update',
  'token:delete',
];
const ROLE_PERMISSIONS: Record<string, string[]> = {
  Owner: [...SELF_SERVICE, 'token:manage'],
  Admin: [...SELF_SERVICE, 'token:manage'],
  Member: SELF_SERVICE,
  // Viewer gets every :read except token:read.
  Viewer: ['test_set:read', 'endpoint:read'],
};

function setRole(role: string) {
  const ambient: AmbientPermissions = {
    permitted_actions: ROLE_PERMISSIONS[role],
    loading: false,
    error: null,
    enabled: true,
  } as AmbientPermissions;
  mockAmbient.mockReturnValue(ambient);
}

const gridProps = jest.fn();
jest.mock('../TokensGrid', () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => {
    gridProps(props);
    return <div data-testid="tokens-grid" />;
  },
}));
jest.mock('../CreateTokenDrawer', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('../TokenDisplay', () => ({ __esModule: true, default: () => null }));
jest.mock('@/hooks/useBulkActionsBridge', () => ({
  useBulkActionsBridge: () => ({
    bulkActionsVisible: true,
    onBulkDelete: jest.fn(),
    handleBulkActionsChange: jest.fn(),
  }),
}));
jest.mock('@/components/layout/PageLayout', () => ({
  PageLayout: ({
    actions,
    children,
  }: {
    actions?: React.ReactNode;
    children: React.ReactNode;
  }) => (
    <div>
      {actions}
      {children}
    </div>
  ),
}));
jest.mock('@/components/common/AccessDenied', () => ({
  __esModule: true,
  default: () => <div data-testid="access-denied" />,
}));
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTokensClient: () => ({}),
  })),
}));

describe('TokensPageClient permissions', () => {
  beforeEach(() => gridProps.mockClear());

  it.each(['Member', 'Admin', 'Owner'])(
    '%s sees the page with create, refresh and delete',
    role => {
      setRole(role);
      render(<TokensPageClient initialData={[]} initialTotalCount={0} />);

      expect(screen.queryByTestId('access-denied')).not.toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Create API token' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Delete Tokens' })
      ).toBeInTheDocument();
      expect(gridProps).toHaveBeenLastCalledWith(
        expect.objectContaining({ canCreate: true, canRefresh: true })
      );
    }
  );

  it('Viewer is refused the page', () => {
    setRole('Viewer');
    render(<TokensPageClient initialData={[]} initialTotalCount={0} />);

    expect(screen.getByTestId('access-denied')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Create API token' })
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('tokens-grid')).not.toBeInTheDocument();
  });
});
